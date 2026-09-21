import shutil
from pathlib import Path

from ruamel.yaml import YAML

from edge_containers_cli.__main__ import cli
from edge_containers_cli.logging import log
from tests.conftest import TMPDIR


def run_cli_args(mock_run, args: list[str]) -> str:
    """
    Like mock_run.run_cli, but takes an argument list directly instead of a
    space-joined string, so a value containing spaces/commas/quotes (e.g.
    --desc "a, b") survives intact instead of being split apart.
    """
    mock_run.params = [str(x) for x in args]
    result = mock_run._runner.invoke(cli, mock_run.params)
    if result.exception:
        log.error(mock_run.log)
        raise result.exception
    if len(mock_run.cmd_rsp) > 0:
        log.error(mock_run.log)
        raise AssertionError("not all commands were run")
    return result.stdout


def test_delete(mock_run, ARGOCD, data: Path):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.delete)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")
    mock_run.run_cli("delete bl01t-ea-test-01")


def test_deploy(mock_run, ARGOCD, data: Path):
    mock_run.set_seq(ARGOCD.deploy)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")
    mock_run.run_cli("deploy bl01t-ea-test-01")


def test_deploy_preserves_service_keys(mock_run, ARGOCD, data: Path):
    # THE CRUX: push_values must merge into the existing services.<name>
    # entry rather than replace it wholesale (set_key replaces whatever
    # value it's given at its target key) - a version-only deploy (no
    # --desc) must leave the existing description, labels and any other
    # unrelated field already in the values repo untouched.
    mock_run.set_seq(ARGOCD.deploy)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")

    values_file = TMPDIR / "apps" / "values.yaml"
    values_file.write_text(
        "services:\n"
        "  bl01t-ea-test-01:\n"
        "    enabled: false\n"
        "    description: existing description\n"
        "    labels:\n"
        "      foo: bar\n"
        "    extra: keepme\n"
    )

    mock_run.run_cli("deploy bl01t-ea-test-01")

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"]["bl01t-ea-test-01"]
    assert entry["description"] == "existing description"
    assert entry["labels"] == {"foo": "bar"}
    assert entry["extra"] == "keepme"
    assert entry["enabled"] is True
    assert entry["targetRevision"] == "1.0"


def test_deploy_no_desc_pushes_neither_description_nor_labels(
    mock_run, ARGOCD, data: Path
):
    # A fresh entry with no prior description/labels must not gain them
    # just from a plain `ec deploy` with no --desc.
    mock_run.set_seq(ARGOCD.deploy)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")

    values_file = TMPDIR / "apps" / "values.yaml"

    mock_run.run_cli("deploy bl01t-ea-test-01")

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"]["bl01t-ea-test-01"]
    assert "description" not in entry
    assert "labels" not in entry
    assert entry["enabled"] is True
    assert entry["targetRevision"] == "1.0"


def test_deploy_desc_leaves_labels_untouched(mock_run, ARGOCD, data: Path):
    # `--desc` writes the top-level `description` key and must NEVER write
    # `labels` - the description is now an Application annotation, not a
    # label, so any labels already on the service (including a stale
    # `description` label left over from before this change) survive
    # completely untouched.
    mock_run.set_seq(ARGOCD.deploy_with_desc)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")

    values_file = TMPDIR / "apps" / "values.yaml"
    values_file.write_text(
        "services:\n"
        "  bl01t-ea-test-01:\n"
        "    enabled: false\n"
        "    labels:\n"
        "      description: stale label, never read any more\n"
        "      foo: bar\n"
        "    extra: keepme\n"
    )

    run_cli_args(
        mock_run,
        ["deploy", "bl01t-ea-test-01", "--desc", 'spaces, commas and "quotes"'],
    )

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"]["bl01t-ea-test-01"]
    assert entry["description"] == 'spaces, commas and "quotes"'
    assert entry["labels"] == {
        "description": "stale label, never read any more",
        "foo": "bar",
    }
    assert entry["extra"] == "keepme"
    assert entry["enabled"] is True
    assert entry["targetRevision"] == "1.0"


def test_deploy_desc_empty_clears(mock_run, ARGOCD, data: Path):
    mock_run.set_seq(ARGOCD.deploy_with_desc)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")

    values_file = TMPDIR / "apps" / "values.yaml"
    values_file.write_text(
        "services:\n"
        "  bl01t-ea-test-01:\n"
        "    enabled: false\n"
        "    description: old description\n"
    )

    run_cli_args(mock_run, ["deploy", "bl01t-ea-test-01", "--desc", ""])

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"]["bl01t-ea-test-01"]
    assert entry["description"] == ""


def test_deploy_is_one_commit(mock_run, ARGOCD, data: Path):
    # Whether or not --desc is given, a deploy must push all of its
    # leaf-key changes in a single commit, not one commit per key.
    mock_run.set_seq(ARGOCD.deploy_with_desc)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")

    mock_run.run_cli("deploy bl01t-ea-test-01 --desc new-description")

    commit_count = mock_run.log.count('CMD: git commit -m "Set ')
    assert commit_count == 1


def test_ps_shows_description_from_application_annotation(mock_run, ARGOCD):
    # The Argo reader must get the description from the Application's own
    # annotation, not from the (now description-less) StatefulSet manifest.
    mock_run.set_seq(ARGOCD.ps_with_description)
    res = mock_run.run_cli("ps")
    assert "my nice service" in res


def test_deploy_clears_enabled_override(mock_run, ARGOCD, data: Path):
    # Regression: a lingering `services.X.enabled=false` parameter override
    # (set by `ec stop --no-commit` or Monitor) must be unset by the next
    # deploy, otherwise the redeployed service stays stopped.
    mock_run.set_seq(ARGOCD.deploy_clears_override)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")
    mock_run.run_cli("deploy bl01t-ea-test-01")


def test_logs(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.logs)
    mock_run.run_cli("logs bl01t-ea-test-01")


def test_log_history(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.log_history)
    mock_run.run_cli("log-history bl01t-ea-test-01")


def test_restart(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.restart)
    mock_run.run_cli("restart bl01t-ea-test-01")


def test_start_commit(mock_run, ARGOCD, data: Path):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.start_commit)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")
    mock_run.run_cli("start bl01t-ea-test-01 --commit")


def test_start(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.start)
    mock_run.run_cli("start bl01t-ea-test-01")


def test_stop_commit(mock_run, ARGOCD, data: Path):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.stop_commit)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")
    mock_run.run_cli("stop bl01t-ea-test-01 --commit")


def test_stop(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.stop)
    mock_run.run_cli("stop bl01t-ea-test-01")


def test_ps(mock_run, ARGOCD):
    expect = (
        "╭──────────────────┬─────────┬─────────┬───────┬──────────────────────╮\n"
        "│ name             │ label   │ version │ ready │ deployed             │\n"
        "├──────────────────┼─────────┼─────────┼───────┼──────────────────────┤\n"
        "│ bl01t-ea-test-01 │ service │ main    │ True  │ 2024-07-12T13:52:35Z │\n"
        "╰──────────────────┴─────────┴─────────┴───────┴──────────────────────╯\n"
    )
    mock_run.set_seq(ARGOCD.checks + ARGOCD.manifest_check)
    res = mock_run.run_cli("ps")

    assert res == expect
