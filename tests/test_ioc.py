import shutil
from pathlib import Path

from tests.conftest import TMPDIR


def test_attach(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.attach)
    mock_run.run_cli("ioc attach bl45p-ea-ioc-01")


def test_delete(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.delete)
    mock_run.run_cli("ioc delete bl45p-ea-ioc-01")


def test_template(mock_run, data, ioc):
    mock_run.set_seq(ioc.checks[:1] + ioc.template)
    mock_run.run_cli(f"ioc template {data / 'iocs/bl45p-ea-ioc-01'}")


def test_deploy_local(mock_run, data, ioc):
    mock_run.set_seq(ioc.checks[:1] + ioc.deploy_local)
    mock_run.run_cli(f"ioc deploy-local {data / 'iocs/bl45p-ea-ioc-01'}")


def test_deploy(mock_run, data: Path, ioc):
    mock_run.set_seq(ioc.checks + ioc.deploy)
    # prep what deploy expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "beamline-chart", TMPDIR / "beamline-chart")
    shutil.copytree(data / "iocs", TMPDIR / "iocs")
    mock_run.run_cli("ioc deploy bl45p-ea-ioc-01 2.0")


def test_instances(mock_run, ioc):
    mock_run.set_seq(ioc.instances)
    mock_run.run_cli("ioc instances bl45p-ea-ioc-01")


def test_exec(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.exec)
    mock_run.run_cli("ioc exec bl45p-ea-ioc-01")


def test_log_history(mock_run, ioc):
    mock_run.set_seq(ioc.log_history)
    mock_run.run_cli("ioc log-history bl45p-ea-ioc-01")


def test_logs(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.logs)
    mock_run.run_cli("ioc logs bl45p-ea-ioc-01")


def test_restart(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.restart)
    mock_run.run_cli("ioc restart bl45p-ea-ioc-01")


def test_start(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.start)
    mock_run.run_cli("ioc start bl45p-ea-ioc-01")


def test_stop(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.stop)
    mock_run.run_cli("ioc stop bl45p-ea-ioc-01")


def test_ps(mock_run, ioc):
    mock_run.set_seq(ioc.ps)
    mock_run.run_cli("ps")
