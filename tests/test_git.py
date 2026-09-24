import asyncio
import contextlib
import shlex
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from edge_containers_cli.git import (
    GitError,
    check_chart_dependency_version,
    commit_args,
    del_key,
    resolve_target_revision,
    set_value,
    set_values,
)
from edge_containers_cli.utils import YamlFile

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


# --- deploy_target_revision: group-aware pin removal (ec-268) ------------
#
# `ec deploy <service> <revision>` must not write a redundant per-service
# `targetRevision` when `<revision>` is already the line the service
# follows: `versions[services.<service>.group]` if it has a `group`, else
# `source.targetRevision` (ec-helm-charts#135's own resolution order,
# https://github.com/epics-containers/edge-containers-cli/issues/268).
# `set_values(..., deploy_target_revision=(service_name, requested_version))`
# is the single entry point that decides this - see resolve_target_revision.

SERVICE = "bl01t-ea-test-01"


def test_deploy_target_revision_no_group_equals_global_removes_existing_pin(
    tmp_path, mocker
):
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "source:\n"
        "  repoURL: https://example.invalid/services.git\n"
        "  targetRevision: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "    targetRevision: old-pin\n"
    )
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {f"services.{SERVICE}.enabled": True},
            deploy_target_revision=(SERVICE, "main"),
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"][SERVICE]
    assert "targetRevision" not in entry
    assert entry["enabled"] is True  # never left as `null`/absent
    assert entry == {"enabled": True}

    # No `enabled` write was actually needed (already true) - the whole
    # commit is the removal, so the message reads as a removal, not a
    # no-op "Set" with nothing in it.
    commit_tokens = _commit_tokens(calls)
    assert (
        commit_tokens[-1] == f"Remove services.{SERVICE}.targetRevision in values.yaml"
    )


def test_deploy_target_revision_no_group_equals_global_never_creates_pin(
    tmp_path, mocker
):
    # A service with only a bare (null) entry - valid YAML shorthand for
    # "use every default", the same shape set_values' require_keys
    # handling already treats as an empty mapping (see
    # test_set_values_require_keys_accepts_null_intermediate): deploying
    # to the revision it would follow anyway must create only the keys
    # actually asked for (enabled) - never an explicit targetRevision.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        f"source:\n  targetRevision: main\nservices:\n  {SERVICE}:\n"
    )
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {f"services.{SERVICE}.enabled": True},
            deploy_target_revision=(SERVICE, "main"),
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    assert written["services"][SERVICE] == {"enabled": True}


def test_deploy_target_revision_group_equals_versions_removes_pin(tmp_path, mocker):
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "source:\n"
        "  targetRevision: main\n"
        "versions:\n"
        "  daq: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "    group: daq\n"
        "    targetRevision: main\n"
    )
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {f"services.{SERVICE}.enabled": True},
            deploy_target_revision=(SERVICE, "main"),
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"][SERVICE]
    assert "targetRevision" not in entry
    assert entry["group"] == "daq"  # group is read, never touched


def test_deploy_target_revision_group_differs_writes_pin(tmp_path, mocker):
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "source:\n"
        "  targetRevision: main\n"
        "versions:\n"
        "  daq: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "    group: daq\n"
    )
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {f"services.{SERVICE}.enabled": True},
            deploy_target_revision=(SERVICE, "release/2026-1"),
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"][SERVICE]
    assert entry["targetRevision"] == "release/2026-1"
    assert entry["group"] == "daq"


def test_deploy_target_revision_adhoc_group_name(tmp_path, mocker):
    # Group names are arbitrary, not just daq/techui - an ad-hoc line
    # (e.g. for a slice test) is a supported pattern, never hard-coded.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "source:\n"
        "  targetRevision: main\n"
        "versions:\n"
        "  motion-fix: fix-motor-timeouts\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "    group: motion-fix\n"
        "    targetRevision: fix-motor-timeouts\n"
    )
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {f"services.{SERVICE}.enabled": True},
            deploy_target_revision=(SERVICE, "fix-motor-timeouts"),
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    assert "targetRevision" not in written["services"][SERVICE]


def test_deploy_target_revision_unknown_group_raises(tmp_path, mocker):
    # The group has no entry in `versions` at all - the chart render would
    # fail on this regardless, so refuse clearly rather than silently
    # writing or silently dropping the pin.
    values_file = tmp_path / "values.yaml"
    before = (
        "source:\n"
        "  targetRevision: main\n"
        "versions:\n"
        "  daq: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "    group: no-such-group\n"
    )
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    with pytest.raises(GitError, match="no-such-group"):
        _run(
            set_values(
                REPO_URL,
                Path("values.yaml"),
                {f"services.{SERVICE}.enabled": True},
                deploy_target_revision=(SERVICE, "main"),
            )
        )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)
    assert not any(c == "git push" for c in calls)


def test_deploy_target_revision_group_with_no_versions_key_raises(tmp_path, mocker):
    # Same refusal when `versions` is missing entirely, not just missing
    # this one group's entry.
    values_file = tmp_path / "values.yaml"
    before = (
        "source:\n"
        "  targetRevision: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "    group: daq\n"
    )
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    with pytest.raises(GitError, match="daq"):
        _run(
            set_values(
                REPO_URL,
                Path("values.yaml"),
                {f"services.{SERVICE}.enabled": True},
                deploy_target_revision=(SERVICE, "main"),
            )
        )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)


def test_deploy_target_revision_no_versions_no_group_backward_compatible(
    tmp_path, mocker
):
    # A deployment repo shaped exactly as before ec-helm-charts#135 (no
    # `versions`, no service ever has a `group`): the only comparison
    # available is against `source.targetRevision`, and a version that
    # differs from it is written exactly as it always was.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        f"source:\n  targetRevision: main\nservices:\n  {SERVICE}:\n    enabled: true\n"
    )
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {f"services.{SERVICE}.enabled": True},
            deploy_target_revision=(SERVICE, "custom-version"),
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    assert written["services"][SERVICE]["targetRevision"] == "custom-version"


def test_deploy_target_revision_no_source_key_always_writes(tmp_path, mocker):
    # No top-level `source.targetRevision` at all (shouldn't happen in a
    # real deployment repo, but resolve_target_revision must fail safe,
    # not crash or silently drop a pin it can't prove is redundant).
    file_data = YamlFile(_write_minimal(tmp_path, SERVICE))
    assert resolve_target_revision(file_data, SERVICE, "main") == "main"


def _write_minimal(tmp_path: Path, service: str) -> Path:
    values_file = tmp_path / "values-minimal.yaml"
    values_file.write_text(f"services:\n  {service}:\n    enabled: true\n")
    return values_file


# --- remove_keys: drop `enabled` entirely rather than writing it ---------
#
# The chart defaults `services.<svc>.enabled` to true and only acts on an
# explicit `false`, so `ec deploy`/`ec start --commit` must remove the key
# (whatever it currently holds) rather than ever writing `enabled: true` -
# `ec stop --commit` is the only path left that writes it, and only to
# `false`. `set_values(..., remove_keys=[...])` is the entry point both
# deploy and start use for this.


def test_set_values_remove_keys_removes_present_key(tmp_path, mocker):
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        f"services:\n  {SERVICE}:\n    enabled: true\n    extra: keepme\n"
    )
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"][SERVICE]
    assert "enabled" not in entry
    assert entry["extra"] == "keepme"

    commit_tokens = _commit_tokens(calls)
    assert commit_tokens[-1] == f"Remove services.{SERVICE}.enabled in values.yaml"
    assert any(c == "git push" for c in calls)


def test_set_values_remove_keys_absent_key_is_a_noop(tmp_path, mocker):
    # Deploying a service that's already enabled (no explicit key at all)
    # must not create a spurious commit just to "remove" nothing.
    values_file = tmp_path / "values.yaml"
    before = f"services:\n  {SERVICE}:\n    extra: keepme\n"
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)
    assert not any(c == "git push" for c in calls)


def test_set_values_remove_keys_refuses_unknown_service(tmp_path, mocker):
    # THE CASE THAT MATTERS MOST (edge-containers-cli#271 regression): the
    # service has no `services.<name>` entry at all - not merely a missing
    # `enabled` leaf on an existing entry (the no-op case above). A
    # mistyped or never-deployed service name must fail loudly, not be
    # swallowed as "nothing to remove" and report success with nothing
    # written.
    values_file = tmp_path / "values.yaml"
    before = "services:\n  some-other-service:\n    enabled: true\n"
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    with pytest.raises(GitError, match=SERVICE):
        _run(
            set_values(
                REPO_URL,
                Path("values.yaml"),
                {},
                remove_keys=[f"services.{SERVICE}.enabled"],
            )
        )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)
    assert not any(c == "git push" for c in calls)


def test_set_values_refuses_unknown_service_when_writing_a_key(tmp_path, mocker):
    # Same refusal as test_set_values_remove_keys_refuses_unknown_service,
    # reached through the other write path `set_values` has: an ordinary
    # `keys` entry (e.g. a targetRevision pin that differs from the line,
    # so it's written rather than removed) for a service with no
    # `services.<name>` entry at all must raise GitError too, not a bare
    # YamlFileError that escapes uncaught.
    values_file = tmp_path / "values.yaml"
    before = "services:\n  some-other-service:\n    enabled: true\n"
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    with pytest.raises(GitError, match=SERVICE):
        _run(
            set_values(
                REPO_URL,
                Path("values.yaml"),
                {f"services.{SERVICE}.targetRevision": "custom-version"},
            )
        )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)
    assert not any(c == "git push" for c in calls)


def test_set_values_remove_keys_true_or_false_both_removed(tmp_path, mocker):
    # "deploy means run it" - an explicit `enabled: false` left over from a
    # committed stop is just as much removed by a deploy as `enabled: true`
    # would be; the value never matters, only that the key is dropped.
    for existing_value in ("true", "false"):
        values_file = tmp_path / "values.yaml"
        values_file.write_text(
            f"services:\n  {SERVICE}:\n    enabled: {existing_value}\n"
        )
        _mock_shell(mocker, tmp_path)

        _run(
            set_values(
                REPO_URL,
                Path("values.yaml"),
                {},
                remove_keys=[f"services.{SERVICE}.enabled"],
            )
        )

        written = YAML(typ="safe").load(values_file.read_text())
        assert "enabled" not in written["services"][SERVICE]


def test_set_values_remove_keys_leaves_empty_mapping_as_empty_dict(tmp_path, mocker):
    # A service whose only key was `enabled` must serialise as `{}`, never
    # a bare `null` - Helm v4 drops a null-valued key, which would prune
    # the service from the chart's render entirely.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(f"services:\n  {SERVICE}:\n    enabled: true\n")
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    assert values_file.read_text() == f"services:\n  {SERVICE}: {{}}\n"


def test_set_values_remove_keys_combines_with_deploy_target_revision(tmp_path, mocker):
    # A real `ec deploy` call: enabled is dropped via remove_keys in the
    # same commit that resolve_target_revision decides to drop the
    # redundant targetRevision pin in - both land in one commit, and an
    # entry left with neither key serialises as `{}`.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "source:\n"
        "  targetRevision: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: false\n"
        "    targetRevision: old-pin\n"
    )
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            deploy_target_revision=(SERVICE, "main"),
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    assert written["services"][SERVICE] == {}

    commit_tokens = _commit_tokens(calls)
    assert commit_tokens[2] == "-m"
    assert commit_tokens[3].startswith("Remove ")


# --- comments around a removed key ---------------------------------------
#
# ruamel keeps the comment lines that follow a key's value attached to that
# key, and the comment lines above a mapping's first key on the mapping
# itself. Removing a key (every deploy removes `enabled`, and at the line
# revision also the pin) must neither take a following section's comments
# with it nor leave a comment where it turns the emptied entry into
# unparseable YAML.


def test_set_values_emptied_entry_with_leading_comment_stays_valid(tmp_path, mocker):
    # b01-1-deployment's b01-1-tiled shape: a parked pin commented out
    # above the live one, which is the entry's only key. Deploying at the
    # line revision empties the entry - the file written must still parse
    # and keep the parked pin.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "source:\n"
        "  targetRevision: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    #targetRevision: enable-tiled\n"
        "    targetRevision: hyperrealist/tiled-test\n"
        "  other-service:\n"
        "    enabled: false\n"
    )
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            deploy_target_revision=(SERVICE, "hyperrealist/tiled-test"),
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )
    # the pin differs from the line, so it was rewritten in place - now
    # deploy at the line revision to empty the entry
    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            deploy_target_revision=(SERVICE, "main"),
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    text = values_file.read_text()
    written = YAML(typ="safe").load(text)
    assert written["services"] == {SERVICE: {}, "other-service": {"enabled": False}}
    assert "#targetRevision: enable-tiled" in text
    assert any(c.startswith("git commit") for c in calls)


def test_set_values_keeps_section_comment_after_removed_key(tmp_path, mocker):
    # i19-deployment's shape: a blank line and a section header follow the
    # last key of the entry above it. Removing that key must leave the
    # header where it was.
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
        "\n"
        "  # DAQ services, targeting main in i19-services (default)\n"
        "  daq-service:\n"
        "    group: daq\n"
    )
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    assert values_file.read_text() == (
        "services:\n"
        f"  {SERVICE}: {{}}\n"
        "\n"
        "  # DAQ services, targeting main in i19-services (default)\n"
        "  daq-service:\n"
        "    group: daq\n"
    )


@pytest.mark.parametrize(
    "before, key, after",
    [
        pytest.param(
            "services:\n"
            "  svc-a:\n"
            "    description: keep\n"
            "    enabled: true  # removed with its line\n"
            "  # introduces svc-b\n"
            "  svc-b: {}\n",
            "services.svc-a.enabled",
            "services:\n"
            "  svc-a:\n"
            "    description: keep\n"
            "  # introduces svc-b\n"
            "  svc-b: {}\n",
            id="last-key-with-sibling-before",
        ),
        pytest.param(
            "services:\n"
            "  svc-a:\n"
            "    enabled: true\n"
            "    # about description\n"
            "    description: keep\n",
            "services.svc-a.enabled",
            "services:\n  svc-a:\n    # about description\n    description: keep\n",
            id="first-key-comment-introduces-kept-key",
        ),
        pytest.param(
            "services:\n"
            "  svc-a:\n"
            "    description: keep\n"
            "    labels:\n"
            "      team: x\n"
            "    enabled: true\n"
            "\n"
            "  # ---- DAQ services ----\n"
            "  svc-b:\n"
            "    group: daq\n",
            "services.svc-a.enabled",
            "services:\n"
            "  svc-a:\n"
            "    description: keep\n"
            "    labels:\n"
            "      team: x\n"
            "\n"
            "  # ---- DAQ services ----\n"
            "  svc-b:\n"
            "    group: daq\n",
            id="previous-sibling-is-a-mapping",
        ),
        pytest.param(
            "services:\n"
            "  svc-a:\n"
            "    enabled: true\n"
            "  svc-b:\n"
            "    description: x\n"
            "\n"
            "  # ---- DAQ services ----\n"
            "  svc-c: {}\n",
            "services.svc-b",
            "services:\n"
            "  svc-a:\n"
            "    enabled: true\n"
            "\n"
            "  # ---- DAQ services ----\n"
            "  svc-c: {}\n",
            id="whole-entry-removed",
        ),
    ],
)
def test_remove_key_keeps_following_comments(tmp_path, before, key, after):
    values_file = tmp_path / "values.yaml"
    values_file.write_text(before)

    file_data = YamlFile(values_file)
    file_data.remove_key(key)
    file_data.dump_file()

    assert values_file.read_text() == after


def _unparseable_dump(self, data, stream):
    stream.write(b"services:\n  svc:\n    #pin\n{}\n  other: {}\n")


@pytest.mark.parametrize(
    "write",
    [
        pytest.param(
            lambda: set_values(
                REPO_URL,
                Path("values.yaml"),
                {},
                remove_keys=[f"services.{SERVICE}.enabled"],
            ),
            id="set_values",
        ),
        pytest.param(
            lambda: set_value(
                REPO_URL, Path("values.yaml"), f"services.{SERVICE}.enabled", False
            ),
            id="set_value",
        ),
        pytest.param(
            lambda: del_key(REPO_URL, Path("values.yaml"), f"services.{SERVICE}"),
            id="del_key",
        ),
    ],
)
def test_unparseable_output_is_never_committed(tmp_path, mocker, write):
    # Whatever ruamel emits is parsed back before anything is written or
    # committed - output that doesn't parse raises GitError and leaves the
    # file, the commit and the push alone.
    values_file = tmp_path / "values.yaml"
    before = f"services:\n  {SERVICE}:\n    enabled: true\n"
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)
    mocker.patch("ruamel.yaml.YAML.dump", _unparseable_dump)

    with pytest.raises(GitError, match="values.yaml"):
        _run(write())

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)
    assert not any(c == "git push" for c in calls)


# --- long lines must round-trip untouched --------------------------------
#
# ruamel's default emitter width (80) wraps any line longer than that, even
# one `set_values`/`set_value` never touched - a real deployment repo's
# `source.repoURL` routinely exceeds it. Writing any key must leave every
# other line byte-identical.

LONG_REPO_URL = (
    "https://github.com/epics-containers/some-very-long-organisation-name/"
    "a-services-repo-with-a-rather-long-name.git"
)
assert len(f"  repoURL: {LONG_REPO_URL}") > 80  # the line this guards against


def test_set_values_does_not_rewrap_long_repo_url(tmp_path, mocker):
    values_file = tmp_path / "values.yaml"
    before = (
        "source:\n"
        f"  repoURL: {LONG_REPO_URL}\n"
        "  targetRevision: main\n"
        "services:\n"
        f"  {SERVICE}:\n"
        "    enabled: true\n"
    )
    values_file.write_text(before)
    _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            remove_keys=[f"services.{SERVICE}.enabled"],
        )
    )

    after = values_file.read_text()
    assert f"  repoURL: {LONG_REPO_URL}\n" in after
    assert after == before.replace(
        f"  {SERVICE}:\n    enabled: true\n", f"  {SERVICE}: {{}}\n"
    )


# --- an unquoted float-like pin must never crash a write ------------------
#
# `targetRevision: 1.0` (no quotes) parses as a YAML float. Deploying to a
# version that isn't itself valid float syntax (e.g. "1.0.1") must set it as
# a plain string, not raise from coercing the new value through the old
# scalar's type.


def test_set_value_unquoted_float_pin_with_incompatible_version_does_not_raise(
    tmp_path, mocker
):
    values_file = tmp_path / "values.yaml"
    values_file.write_text(f"services:\n  {SERVICE}:\n    targetRevision: 1.0\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_value(
            REPO_URL,
            Path("values.yaml"),
            f"services.{SERVICE}.targetRevision",
            "1.0.1",
        )
    )

    written = YAML(typ="safe").load(values_file.read_text())
    assert written["services"][SERVICE]["targetRevision"] == "1.0.1"
    assert any(c.startswith("git commit") for c in calls)


def test_set_value_refuses_unknown_service(tmp_path, mocker):
    # `ec stop <svc> --commit` writes through set_value - a service with no
    # `services.<name>` entry must give the same GitError as deploy/start.
    values_file = tmp_path / "values.yaml"
    before = "services:\n  some-other-service:\n    enabled: true\n"
    values_file.write_text(before)
    calls = _mock_shell(mocker, tmp_path)

    with pytest.raises(GitError, match=SERVICE):
        _run(
            set_value(
                REPO_URL, Path("values.yaml"), f"services.{SERVICE}.enabled", False
            )
        )

    assert values_file.read_text() == before
    assert not any(c.startswith("git commit") for c in calls)


def test_commit_args_without_message_keeps_generated_summary_alone():
    assert shlex.split(commit_args("Set foo=bar in values.yaml", None)) == [
        "-m",
        "Set foo=bar in values.yaml",
    ]


def test_commit_args_with_message_puts_note_first():
    # The note is the subject (what a log listing shows) and the
    # generated summary becomes the body, so the machine-readable
    # `Set ...` line survives for anyone grepping the history.
    assert shlex.split(commit_args("Set foo=bar in values.yaml", "rolled back")) == [
        "-m",
        "rolled back",
        "-m",
        "Set foo=bar in values.yaml",
    ]


def test_commit_args_quotes_a_hostile_note():
    # A note is free text straight from the command line, so it reaches
    # the shell the same way the generated summary does and must be
    # quoted just as thoroughly.
    assert shlex.split(commit_args("Set foo=bar in values.yaml", MALICIOUS)) == [
        "-m",
        MALICIOUS,
        "-m",
        "Set foo=bar in values.yaml",
    ]


def test_set_value_records_the_note(tmp_path, mocker):
    (tmp_path / "values.yaml").write_text("foo: old\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(set_value(REPO_URL, Path("values.yaml"), "foo", "new", message=MALICIOUS))

    assert _commit_tokens(calls) == [
        "git",
        "commit",
        "-m",
        MALICIOUS,
        "-m",
        "Set foo=new in values.yaml",
    ]


def test_del_key_records_the_note(tmp_path, mocker):
    (tmp_path / "values.yaml").write_text("foo: old\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(del_key(REPO_URL, Path("values.yaml"), "foo", message="decommissioned"))

    assert _commit_tokens(calls) == [
        "git",
        "commit",
        "-m",
        "decommissioned",
        "-m",
        "Remove foo in values.yaml",
    ]


def test_set_values_records_the_note(tmp_path, mocker):
    (tmp_path / "values.yaml").write_text("foo: old\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL, Path("values.yaml"), {"foo": "new"}, message="ticket EC-123"
        )
    )

    assert _commit_tokens(calls) == [
        "git",
        "commit",
        "-m",
        "ticket EC-123",
        "-m",
        "Set foo=new in values.yaml",
    ]


def test_set_values_records_the_note_on_a_removal_only_commit(tmp_path, mocker):
    # `ec start --commit` and a deploy to the line a service already follows
    # commit nothing but removals - the note must still lead that commit.
    (tmp_path / "values.yaml").write_text("services:\n  svc:\n    enabled: false\n")
    calls = _mock_shell(mocker, tmp_path)

    _run(
        set_values(
            REPO_URL,
            Path("values.yaml"),
            {},
            remove_keys=["services.svc.enabled"],
            message="back after maintenance",
        )
    )

    assert _commit_tokens(calls) == [
        "git",
        "commit",
        "-m",
        "back after maintenance",
        "-m",
        "Remove services.svc.enabled in values.yaml",
    ]
