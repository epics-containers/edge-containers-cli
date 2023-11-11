"""
tests for local docker deployment/management commands
"""

import os
import shutil
from pathlib import Path

from tests.conftest import TMPDIR


def test_attach(mock_run, local):
    mock_run.set_seq(local.setup + local.attach)
    mock_run.run_cli("ioc attach bl45p-ea-ioc-01")


def test_delete(mock_run, local):
    mock_run.set_seq(local.setup + local.delete)
    mock_run.run_cli("ioc delete bl45p-ea-ioc-01")


def test_deploy_local(mock_run, data, local):
    mock_run.set_seq(local.setup + local.deploy_local)
    mock_run.run_cli(f"ioc deploy-local {data / 'iocs/bl45p-ea-ioc-01'}")


def test_deploy(mock_run, data, local):
    mock_run.set_seq(local.setup + local.deploy)
    # prep what deploy expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "iocs", TMPDIR / "iocs")
    mock_run.run_cli("ioc deploy bl45p-ea-ioc-01 2.0")


def test_instances(mock_run, local):
    mock_run.set_seq(local.instances)
    mock_run.run_cli("ioc instances bl45p-ea-ioc-01")


def test_exec(mock_run, local):
    mock_run.set_seq(local.setup + local.exec)
    mock_run.run_cli("ioc exec bl45p-ea-ioc-01")


def test_logs(mock_run, local):
    mock_run.set_seq(local.setup + local.logs)
    mock_run.run_cli("ioc logs bl45p-ea-ioc-01")


def test_restart(mock_run, local):
    mock_run.set_seq(local.setup + local.restart)
    mock_run.run_cli("ioc restart bl45p-ea-ioc-01")


def test_start(mock_run, local):
    mock_run.set_seq(local.setup + local.start)
    mock_run.run_cli("ioc start bl45p-ea-ioc-01")


def test_stop(mock_run, local):
    mock_run.set_seq(local.setup + local.stop)
    mock_run.run_cli("ioc stop bl45p-ea-ioc-01")


def test_ps(mock_run, local):
    mock_run.set_seq(local.setup + local.ps)
    mock_run.run_cli("ps")


def test_validate(mock_run, local, data):
    mock_run.set_seq(local.setup + local.validate)
    os.chdir(Path(__file__).parent)
    mock_run.run_cli(f"ioc validate {data / 'iocs/bl45p-ea-ioc-01'}")
