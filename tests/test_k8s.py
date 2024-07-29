import shutil
from pathlib import Path

from tests.conftest import TMPDIR


def test_attach(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.attach)
    mock_run.run_cli("attach bl01t-ea-test-01")


# def test_delete(mock_run, K8S):
#     mock_run.set_seq(K8S.checks + K8S.delete)
#     mock_run.run_cli("delete bl01t-ea-test-01")


# def test_template(mock_run, data, K8S):
#     mock_run.set_seq(K8S.checks[:1] + K8S.template)
#     mock_run.run_cli(f"template {data / 'bl01t/services/bl01t-ea-test-01'}")


# def test_deploy_local(mock_run, data, K8S):
#     mock_run.set_seq(K8S.checks[:1] + K8S.deploy_local)
#     mock_run.run_cli(f"deploy-local {data / 'bl01t/services/bl01t-ea-test-01'}")


# def test_deploy(mock_run, data: Path, K8S):
#     mock_run.set_seq(K8S.deploy)
#     # prep what deploy expects to find after it cloned bl01t repo
#     TMPDIR.mkdir()
#     shutil.copytree(data / "bl01t/services", TMPDIR / "services")
#     mock_run.run_cli("deploy bl01t-ea-test-01 2.0")


# def test_deploy_path(mock_run, data: Path, K8S):
#     mock_run.set_seq(K8S.deploy)
#     # prep what deploy expects to find after it cloned bl01t repo
#     TMPDIR.mkdir()
#     shutil.copytree(data / "bl01t/services", TMPDIR / "services")
#     mock_run.run_cli("deploy services/bl01t-ea-test-01 2.0")


def test_exec(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.exec)
    mock_run.run_cli("exec bl01t-ea-test-01")


def test_logs(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.logs)
    mock_run.run_cli("logs bl01t-ea-test-01")

def test_log_history(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.log_history)
    mock_run.run_cli("log-history bl01t-ea-test-01")


def test_restart(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.restart)
    mock_run.run_cli("restart bl01t-ea-test-01")


def test_start(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.start)
    mock_run.run_cli("start bl01t-ea-test-01")


def test_stop(mock_run, K8S):
    mock_run.set_seq(K8S.checks + K8S.stop)
    mock_run.run_cli("stop bl01t-ea-test-01")


def test_ps(mock_run, K8S):
    mock_run.set_seq(K8S.ps)
    mock_run.run_cli("ps")
