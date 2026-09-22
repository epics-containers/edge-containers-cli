import shutil
from pathlib import Path

from ruamel.yaml import YAML

from tests.conftest import TMPDIR


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
    # --desc) must leave the existing description label, any other label,
    # and any other unrelated field already in the values repo untouched.
    mock_run.set_seq(ARGOCD.deploy)
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    shutil.copytree(data / "bl01t-deployment/apps", TMPDIR / "apps")

    values_file = TMPDIR / "apps" / "values.yaml"
    values_file.write_text(
        "services:\n"
        "  bl01t-ea-test-01:\n"
        "    enabled: false\n"
        "    labels:\n"
        "      description: existing-description\n"
        "      foo: bar\n"
        "    extra: keepme\n"
    )

    mock_run.run_cli("deploy bl01t-ea-test-01")

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"]["bl01t-ea-test-01"]
    assert entry["labels"] == {"description": "existing-description", "foo": "bar"}
    assert entry["extra"] == "keepme"
    assert entry["enabled"] is True
    assert entry["targetRevision"] == "1.0"


def test_deploy_desc_preserves_other_labels(mock_run, ARGOCD, data: Path):
    # `--desc` writes only the labels.description leaf key - any other
    # label already on the service must survive.
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
        "      description: old-description\n"
        "      foo: bar\n"
        "    extra: keepme\n"
    )

    mock_run.run_cli("deploy bl01t-ea-test-01 --desc new-description")

    written = YAML(typ="safe").load(values_file.read_text())
    entry = written["services"]["bl01t-ea-test-01"]
    assert entry["labels"] == {"description": "new-description", "foo": "bar"}
    assert entry["extra"] == "keepme"
    assert entry["enabled"] is True
    assert entry["targetRevision"] == "1.0"


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
