"""
tests for local docker deployment/management commands
"""

import os
import shutil
from pathlib import Path

from tests.conftest import TMPDIR


def test_attach(mock_run, local):
    mock_run.set_seq(local.setup + local.attach)
    mock_run.run_cli("attach bl01t-ea-test-01")


def test_delete(mock_run, local):
    mock_run.set_seq(local.setup + local.delete)
    mock_run.run_cli("delete bl01t-ea-test-01")


def test_deploy_local(mock_run, data, local):
    mock_run.set_seq(local.setup + local.deploy_local)
    mock_run.run_cli(f"deploy-local {data / 'bl01t/services/bl01t-ea-test-01'}")


def test_deploy(mock_run, data, local):
    mock_run.set_seq(local.setup + local.deploy)
    # prep what deploy expects to find after it cloned bl01t repo
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t/services", TMPDIR / "services")
    mock_run.run_cli("deploy bl01t-ea-test-01 2.0")


def test_instances(mock_run, local, data: Path):
    mock_run.set_seq(local.instances)
    # prep what instances expects to find after it cloned bl01t repo
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t/services", TMPDIR / "services")
    mock_run.run_cli("instances bl01t-ea-test-01")


def test_exec(mock_run, local):
    mock_run.set_seq(local.setup + local.exec)
    mock_run.run_cli("exec bl01t-ea-test-01")


def test_logs(mock_run, local):
    mock_run.set_seq(local.setup + local.logs)
    mock_run.run_cli("logs bl01t-ea-test-01")


def test_restart(mock_run, local):
    mock_run.set_seq(local.setup + local.restart)
    mock_run.run_cli("restart bl01t-ea-test-01")


def test_start(mock_run, local):
    mock_run.set_seq(local.setup + local.start)
    mock_run.run_cli("start bl01t-ea-test-01")


def test_stop(mock_run, local):
    mock_run.set_seq(local.setup + local.stop)
    mock_run.run_cli("stop bl01t-ea-test-01")


def test_ps(mock_run, local):
    mock_run.set_seq(local.setup + local.ps)
    mock_run.run_cli("ps")


def test_validate(mock_run, local, data):
    mock_run.set_seq(local.setup + local.validate)
    os.chdir(Path(__file__).parent)
    mock_run.run_cli(f"validate {data / 'bl01t/services/bl01t-ea-test-01'}")
