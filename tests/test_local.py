"""
tests for local docker deployment/management commands
"""

import shutil

from tests.conftest import TMPDIR


def test_attach(mock_run, local):
    mock_run.set_seq(local.attach)
    mock_run.run_cli("ioc attach bl45p-ea-ioc-01")


def test_delete(mock_run, local):
    mock_run.set_seq(local.delete)
    mock_run.run_cli("ioc delete bl45p-ea-ioc-01")


def test_deploy_local(mock_run, data, local):
    mock_run.set_seq(local.deploy_local)
    mock_run.run_cli(f"ioc deploy-local {data / 'iocs/bl45p-ea-ioc-01'}")


def test_deploy(mock_run, data, local):
    mock_run.set_seq(local.deploy)
    # prep what deploy expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "iocs", TMPDIR / "iocs")
    mock_run.run_cli("ioc deploy bl45p-ea-ioc-01 2.0")


def test_instances(mock_run, local):
    mock_run.set_seq(local.instances)
    mock_run.run_cli("ioc instances bl45p-ea-ioc-01")


def test_exec(mock_run, local):
    mock_run.set_seq(local.exec)
    mock_run.run_cli("ioc exec bl45p-ea-ioc-01")


def test_logs(mock_run, local):
    mock_run.set_seq(local.logs)
    mock_run.run_cli("ioc logs bl45p-ea-ioc-01")


def test_restart(mock_run, local):
    mock_run.set_seq(local.restart)
    mock_run.run_cli("ioc restart bl45p-ea-ioc-01")


def test_start(mock_run, local):
    mock_run.set_seq(local.start)
    mock_run.run_cli("ioc start bl45p-ea-ioc-01")


def test_stop(mock_run, local):
    mock_run.set_seq(local.stop)
    mock_run.run_cli("ioc stop bl45p-ea-ioc-01")