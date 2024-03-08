import shutil
from pathlib import Path

from tests.conftest import TMPDIR


def test_attach(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.attach)
    mock_run.run_cli("attach bl45p-ea-ioc-01")


def test_delete(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.delete)
    mock_run.run_cli("delete bl45p-ea-ioc-01")


def test_template(mock_run, data, ioc):
    mock_run.set_seq(ioc.checks[:1] + ioc.template)
    mock_run.run_cli(f"template {data / 'services/bl45p-ea-ioc-01'}")


def test_deploy_local(mock_run, data, ioc):
    mock_run.set_seq(ioc.checks[:1] + ioc.deploy_local)
    mock_run.run_cli(f"deploy-local {data / 'services/bl45p-ea-ioc-01'}")


def test_deploy(mock_run, data: Path, ioc):
    mock_run.set_seq(ioc.deploy)
    # prep what deploy expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "services", TMPDIR / "services")
    mock_run.run_cli("deploy bl45p-ea-ioc-01 2.0")


def test_deploy_path(mock_run, data: Path, ioc):
    mock_run.set_seq(ioc.deploy)
    # prep what deploy expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "services", TMPDIR / "services")
    mock_run.run_cli("deploy bl45p/services/bl45p-ea-ioc-01 2.0")


def test_list(mock_run, ioc, data: Path):
    mock_run.set_seq(ioc.instances)
    # prep what instances expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "services", TMPDIR / "services")
    mock_run.run_cli("list")


def test_instances(mock_run, ioc, data: Path):
    mock_run.set_seq(ioc.instances)
    # prep what instances expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "services", TMPDIR / "services")
    mock_run.run_cli("instances bl45p-ea-ioc-01")


def test_exec(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.exec)
    mock_run.run_cli("exec bl45p-ea-ioc-01")


def test_log_history(mock_run, ioc):
    mock_run.set_seq(ioc.log_history)
    mock_run.run_cli("log-history bl45p-ea-ioc-01")


def test_logs(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.logs)
    mock_run.run_cli("logs bl45p-ea-ioc-01")


def test_restart(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.restart)
    mock_run.run_cli("restart bl45p-ea-ioc-01")


def test_start(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.start)
    mock_run.run_cli("start bl45p-ea-ioc-01")


def test_stop(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.stop)
    mock_run.run_cli("stop bl45p-ea-ioc-01")


def test_ps(mock_run, ioc):
    mock_run.set_seq(ioc.ps)
    mock_run.run_cli("ps")
