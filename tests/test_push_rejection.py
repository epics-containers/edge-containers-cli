"""
Regression test for a silent-failure bug: when a `git push` to the
deployment repo is rejected (e.g. a protected `main` branch requiring a
PR), every `ec` command that commits and pushes (deploy, delete, ...)
must fail loudly - a clear error, including git's own rejection reason,
and a non-zero exit code.

This is deliberately an end-to-end test against a REAL git remote (a
local bare repo with a `pre-receive` hook that rejects every push, the
same mechanism a GitHub branch-protection ruleset uses), run through the
actual `python -m edge_containers_cli` entry point as a subprocess - not
through `CliRunner.invoke`, which bypasses the very code path where this
bug lives (`ErrorHandlingTyper.__call__`, only reached when the Typer app
is *called*, not when `typer.testing.CliRunner` converts it to a click
Command and invokes that directly).

Root cause: `ErrorHandlingTyper.__call__` in `edge_containers_cli/cli.py`
caught `CommandError`/`ShellError`/`GitError`, logged it, then
constructed `typer.Exit(1)` without raising it - so the exception was
built and discarded, the process fell through to a normal return, and
`ec` exited 0 even though nothing was pushed. This was introduced in
748e9a7, "Refactor for argocd (#160)", so it is a bug in the released
CLI, not something new.

`delete` and `set-desc` are exercised here: both commit+push through the
same top-level `ErrorHandlingTyper` error handling, but via different
`git.py` helpers (`del_key` vs `set_values`, through `push_remove_key`/
`push_values` in `argo_commands.py`), so together they cover both write
paths `deploy` also shares (`set_value`/`set_values`). A second scenario
per command would only re-test the same two lines, so one of each is
enough.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git is required to build a real remote for this test",
)


def _init_rejecting_remote(tmp_path: Path) -> Path:
    """
    A real local git remote that accepts an initial push (to seed
    content, as if the deployment repo already existed) and then rejects
    every subsequent push, the way a protected branch's ruleset does -
    with a git-shaped rejection message on stderr.
    """
    bare = tmp_path / "deployment.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(bare)], check=True)
    # Pin the bare repo's HEAD to `main` regardless of the environment's
    # `init.defaultBranch` (still "master" on GitHub Actions' runner
    # image, but "main" on machines configured to override it): the
    # production code clones with no `-b`, so it follows HEAD, and if
    # HEAD points at a branch that's never actually pushed to (here
    # "master") that clone comes back empty, failing with
    # "No such file or directory: 'apps/values.yaml'" before the push is
    # even attempted - this is unrelated to the push-rejection behaviour
    # under test. `symbolic-ref` accepts a target that doesn't exist yet,
    # so this is safe before anything has been pushed.
    subprocess.run(
        ["git", "--git-dir", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"],
        check=True,
    )

    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "--quiet", str(bare), str(seed)], check=True)
    apps = seed / "apps"
    apps.mkdir()
    (apps / "values.yaml").write_text(
        'services:\n  bl01t-ea-test-01:\n    enabled: true\n    targetRevision: "1.0"\n'
    )
    (apps / "Chart.yaml").write_text(
        "apiVersion: v2\n"
        "name: applications\n"
        "version: 0.1.1\n"
        "appVersion: '1.0'\n"
        "dependencies:\n"
        "  - name: argocd-apps\n"
        "    version: 5.10.0\n"
    )
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com"}
    env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_COMMITTER_EMAIL"] = "t@example.com"
    subprocess.run(["git", "add", "."], cwd=seed, check=True, env=env)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "seed"], cwd=seed, check=True, env=env
    )
    subprocess.run(
        ["git", "push", "--quiet", "origin", "HEAD:main"], cwd=seed, check=True, env=env
    )

    # Arm branch protection *after* seeding, exactly like a real ruleset:
    # it never blocked the repo's initial content, only later pushes.
    hook = bare / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        'echo "remote: error: GH013: Repository rule violations found for '
        'refs/heads/main." >&2\n'
        'echo "remote: Cannot push to a protected branch, use a pull '
        'request." >&2\n'
        "exit 1\n"
    )
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    return bare


def _write_fake_argocd(bin_dir: Path, bare_repo: Path) -> None:
    """
    A stand-in `argocd` binary. `ec delete` shells out to it purely to
    validate the target, list/check the service, look up which git
    repo/path backs it, and (after the push) unset patched values and
    refresh - none of that is what this test is about, so each lookup is
    answered with fixed, minimal output. The actual git clone/edit/
    commit/push against `bare_repo` is real.

    Matched in order of specificity, since several of these commands
    share substrings (e.g. every "app get ..." call):
      1. `app list` (service existence check)
      2. `--show-params ... -o json` (post-push patch lookup)
      3. `-o yaml` (source repoURL/path lookup)
      4. anything else (`app get` for target validation, `app unset`,
         `--refresh`) just succeeds.
    """
    script = bin_dir / "argocd"
    script.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  *"app list"*)\n'
        "    printf '%s\\n' '- metadata:' '    name: bl01t-ea-test-01'\n"
        "    ;;\n"
        '  *"--show-params"*"-o json"*)\n'
        "    printf '%s\\n' '{}'\n"
        "    ;;\n"
        '  *"-o yaml"*)\n'
        "    printf '%s\\n' \\\n"
        "      'metadata:' '  name: bl01t-ea-test-01' '  annotations: {}' \\\n"
        "      'spec:' '  source:' \\\n"
        f"      '    repoURL: file://{bare_repo}' '    path: apps'\n"
        "    ;;\n"
        "  *)\n"
        "    exit 0\n"
        "    ;;\n"
        "esac\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)


def _run_ec(
    tmp_path: Path, bin_dir: Path, args: list[str]
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "EC_CLI_BACKEND": "ARGOCD",
        # `ec` makes its own clone (in git.py's del_key/set_values) and
        # commits to it directly - unlike the seed repo above, that
        # clone/commit is real production code, not test setup, so it
        # can't be handed an env dict here; it inherits this subprocess's
        # env instead. A dev machine's global git config usually has an
        # identity set, but the GitHub Actions runner image doesn't, so
        # without this the commit fails with "Author identity unknown"
        # before it ever reaches the push this test is actually about.
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    return subprocess.run(
        [sys.executable, "-m", "edge_containers_cli", "-t", "bl01t/bl01t-ea-test-01"]
        + args,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["delete", "bl01t-ea-test-01", "-y"], id="delete"),
        pytest.param(
            ["set-desc", "bl01t-ea-test-01", "new-description", "-y"], id="set-desc"
        ),
    ],
)
def test_rejected_push_fails_loudly(tmp_path: Path, args: list[str]):
    bare_repo = _init_rejecting_remote(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_argocd(bin_dir, bare_repo)

    result = _run_ec(tmp_path, bin_dir, args)

    # Loud: git's own rejection reason reaches the user.
    assert "GH013" in result.stderr, result.stderr
    assert "protected branch" in result.stderr, result.stderr
    assert "rejected" in result.stderr or "declined" in result.stderr, result.stderr

    # Non-zero: the caller (a script, CI, a human checking $?) can tell
    # this failed - this was the actual bug: exit code was 0.
    assert result.returncode != 0, (
        f"exit code was {result.returncode}, expected non-zero; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    # And nothing was actually written to the remote.
    verify = tmp_path / "verify"
    subprocess.run(["git", "clone", "--quiet", str(bare_repo), str(verify)], check=True)
    values = (verify / "apps" / "values.yaml").read_text()
    assert "services:" in values
    assert "bl01t-ea-test-01" in values
