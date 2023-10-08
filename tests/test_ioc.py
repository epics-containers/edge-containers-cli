import mock

from tests.conftest import MockRun

cmd = MockRun.cmd
rsp = MockRun.rsp


def test_attach(mock_run, ioc):
    mock_run.set_response(ioc.checks + ioc.attach)
    mock_run.run_cli("ioc", "attach", "bl45p-ea-ioc-01")


@mock.patch("typer.confirm")
def test_delete(mock_typer, mock_run, ioc):
    mock_typer.return_value = True
    mock_run.set_response(ioc.checks + ioc.delete)
    mock_run.run_cli("ioc", "delete", "bl45p-ea-ioc-01")


@mock.patch("typer.confirm")
def test_template(mock_typer, mock_run, data, ioc):
    mock_typer.return_value = True
    mock_run.set_response(ioc.checks + ioc.template)
    mock_run.run_cli("ioc", "template", data / "iocs/bl45p-ea-ioc-01")


def test_instances(mock_run, ioc):
    mock_run.set_response(ioc.checks + ioc.instances)
    mock_run.run_cli("ioc", "instances", "bl45p-ea-ioc-01")
