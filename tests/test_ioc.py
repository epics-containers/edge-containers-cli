import shutil

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


def test_deploy(mock_run, data, ioc):
    mock_run.set_seq(ioc.checks + ioc.deploy)
    # prep what deploy expects to find after it cloned bl45p repo
    TMPDIR.mkdir()
    shutil.copytree(data / "beamline-chart", TMPDIR / "beamline-chart")
    mock_run.run_cli("ioc deploy bl45p-ea-ioc-01 2.0")


def test_instances(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.instances)
    mock_run.run_cli("ioc instances bl45p-ea-ioc-01")


def test_exec(mock_run, ioc):
    mock_run.set_seq(ioc.checks + ioc.exec)
    mock_run.run_cli("ioc exec bl45p-ea-ioc-01")
