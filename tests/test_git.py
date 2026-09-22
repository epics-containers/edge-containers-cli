import asyncio
import contextlib
import shlex
from pathlib import Path

import pytest

from edge_containers_cli.git import (
    GitError,
    check_chart_dependency_version,
    del_key,
    set_value,
    set_values,
)

DEPENDENCY = "argocd-apps"
MIN_VERSION = "5.10.0"
FEATURE = "description"

REPO_URL = "https://example.invalid/deployment.git"


@contextlib.contextmanager
def _fixed_workdir(path: Path):
    """A `new_workdir` stand-in that reuses an existing directory (a
    pytest `tmp_path`) instead of a fresh `tempfile.mkdtemp()`, so a test
    can seed the file the mocked `git clone` would otherwise have
    produced."""
    yield path


def _run(coro):
    return asyncio.run(coro)


def _mock_shell(mocker, tmp_path: Path) -> list[str]:
    """Patch git.py's `shell.run_command` and `new_workdir`, returning the
    list that every issued command is recorded into, in order."""
    calls: list[str] = []

    async def fake_run_command(command, *args, **kwargs):
        calls.append(command)
        return ""

    mocker.patch("edge_containers_cli.git.shell.run_command", fake_run_command)
    mocker.patch(
        "edge_containers_cli.git.new_workdir",
        lambda: _fixed_workdir(tmp_path),
    )
    return calls


def _write_chart(chart_dir: Path, dependencies_yaml: str) -> None:
    (chart_dir / "Chart.yaml").write_text(
        "apiVersion: v2\n"
        "name: applications\n"
        "version: 0.1.1\n"
        "appVersion: '1.0'\n"
        "\n" + dependencies_yaml
    )


def _check(chart_dir: Path) -> None:
    check_chart_dependency_version(chart_dir, DEPENDENCY, MIN_VERSION, FEATURE)


def test_old_pinned_version_refused(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 5.7.0\n",
    )
    with pytest.raises(GitError) as exc:
        _check(tmp_path)
    message = str(exc.value)
    assert DEPENDENCY in message
    assert "5.7.0" in message  # what was found
    assert MIN_VERSION in message  # what is needed
    assert "version-only deploy" in message  # unaffected escape hatch


def test_exact_min_version_passes(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 5.10.0\n",
    )
    _check(tmp_path)  # must not raise


def test_newer_version_passes(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 6.0.0\n",
    )
    _check(tmp_path)  # must not raise


def test_prerelease_of_min_version_passes(tmp_path):
    # A chart maintainer testing a pre-release of the version that
    # introduces the feature must not be refused - only the release
    # segment (major.minor.patch) is compared.
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: 5.10.0-rc1\n",
    )
    _check(tmp_path)  # must not raise


def test_missing_dependency_entry_refused(tmp_path):
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: some-other-chart\n    version: 9.9.9\n",
    )
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_no_dependencies_list_refused(tmp_path):
    _write_chart(tmp_path, "")
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_missing_chart_yaml_refused(tmp_path):
    # No Chart.yaml at all in chart_dir.
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_file_url_dependency_refused(tmp_path):
    # A local dev checkout pinned by path rather than a released version -
    # not special-cased to auto-allow, it fails closed like any other
    # unparsable version.
    _write_chart(
        tmp_path,
        "dependencies:\n  - name: argocd-apps\n    version: file://../argocd-apps\n",
    )
    with pytest.raises(GitError, match=DEPENDENCY):
        _check(tmp_path)


def test_range_version_refused(tmp_path):
    for range_version in ("^5.10.0", ">=5.10.0", ">=5.8.0 <6.0.0", "~5.10.0"):
        _write_chart(
            tmp_path,
            f"dependencies:\n  - name: argocd-apps\n    version: {range_version!r}\n",
        )
        with pytest.raises(GitError, match=DEPENDENCY):
            _check(tmp_path)


# --- shell-injection: commit_msg must never reach the shell unquoted -----
#
# shell.run_command runs its command via asyncio.create_subprocess_shell,
# so a commit message built from caller-supplied text (a key, a value, a
# service description, ...) must be shell-quoted before being embedded in
# `git commit -m ...`, or a description/value containing `"`, `$(...)` or
# `` ` `` could break out of the quoting and run arbitrary shell commands.
# This is checked at all three call sites that build a commit message:
# set_value, set_values (exercised separately via the CLI in
# tests/test_argocd.py) and del_key.

MALICIOUS = 'bad"; $(touch pwned); echo "done'


def _commit_tokens(calls: list[str]) -> list[str]:
    commit_cmds = [c for c in calls if c.startswith("git commit")]
    assert len(commit_cmds) == 1, f"expected exactly one commit, got {commit_cmds}"
    return shlex.split(commit_cmds[0])


def test_set_value_quotes_commit_message(tmp_path, mocker):
    (tmp_path / "values.yaml").write_text("foo: old\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(set_value(REPO_URL, Path("values.yaml"), "foo", MALICIOUS))

    tokens = _commit_tokens(calls)
    # shlex.split recovering exactly ["git", "commit", "-m", <message>]
    # proves the message round-trips as a single literal shell argument -
    # if the quoting were broken (e.g. still double-quoted, unescaped),
    # the embedded `"` and `$(...)` would either split it into more
    # tokens or let the shell substitute `$(...)`.
    assert tokens == [
        "git",
        "commit",
        "-m",
        f"Set foo={MALICIOUS} in values.yaml",
    ]


def test_del_key_quotes_commit_message(tmp_path, mocker):
    # The key itself is what's interpolated into the commit message here,
    # so give it the shell metacharacters (a key naming is a bit
    # contrived, but it's the same commit_msg pattern as set_value/
    # set_values, so it must be just as safe).
    (tmp_path / "values.yaml").write_text(f"{MALICIOUS!r}: old\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(del_key(REPO_URL, Path("values.yaml"), MALICIOUS))

    tokens = _commit_tokens(calls)
    assert tokens == [
        "git",
        "commit",
        "-m",
        f"Remove {MALICIOUS} in values.yaml",
    ]


# --- require_keys on a non-mapping intermediate --------------------------
#
# `set_values(..., require_keys=[...])` exists to stop a caller creating a
# new, partial services.<name> entry for a service that was never
# deployed. A bare `name:` entry is ordinary YAML for "an empty mapping -
# use every default" (t11-deployment's apps/values.yaml has several), so
# it must be accepted and turned into a real mapping the write can land
# in - not confused with a missing key or a genuinely wrong type. A real
# scalar or a list at that path is still refused, just as clearly as
# before, and not left to raise an unrelated, uncaught TypeError instead.


def test_set_values_require_keys_accepts_null_intermediate(tmp_path, mocker):
    values_file = tmp_path / "values.yaml"
    # A sibling service, a comment and a bare (null) target entry, in among
    # other real content, to prove the ruamel round-trip only touches what
    # it's asked to.
    before = (
        "# top-of-file comment\n"
        "services:\n"
        "  bl01t-ea-existing-01:\n"
        "    enabled: true\n"
        "    targetRevision: 1.0\n"
        "  bl01t-ea-test-01:  # uses every default\n"
        "  bl01t-ea-other-01:\n"
        "    enabled: false\n"
    )
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {"services.bl01t-ea-test-01.description": "simulation of 2 motors"},
            require_keys=["services.bl01t-ea-test-01"],
        )
    )

    after = values_file.read_text()
    assert after == (
        "# top-of-file comment\n"
        "services:\n"
        "  bl01t-ea-existing-01:\n"
        "    enabled: true\n"
        "    targetRevision: 1.0\n"
        "  bl01t-ea-test-01:  # uses every default\n"
        "    description: simulation of 2 motors\n"
        "  bl01t-ea-other-01:\n"
        "    enabled: false\n"
    )
    assert any(c.startswith("git commit") for c in calls)
    assert any(c == "git push" for c in calls)


def test_set_values_require_keys_rejects_scalar_intermediate(tmp_path, mocker):
    values_file = tmp_path / "values.yaml"
    before = "services:\n  bl01t-ea-test-01: not-a-mapping\n"
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    with pytest.raises(GitError, match="not a mapping"):
        _run(
            set_values(
                REPO_URL,
                Path("values.yaml"),
                {"services.bl01t-ea-test-01.description": "new description"},
                require_keys=["services.bl01t-ea-test-01"],
            )
        )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)
    assert not any(c == "git push" for c in calls)
