from tests.conftest import MockRun

cmd = MockRun.cmd
rsp = MockRun.rsp


def test_attach(mock_run, ioc):
    mock_run.set_response(ioc.checks + ioc.attach)
    mock_run.run_cli("ioc attach bl45p-ea-ioc-01")


def test_delete(mock_run, ioc):
    mock_run.set_response(ioc.checks + ioc.delete)
    mock_run.run_cli("ioc delete bl45p-ea-ioc-01")


def test_template(mock_run, data, ioc):
    mock_run.set_response(ioc.checks[:1] + ioc.template)
    mock_run.run_cli(f"ioc template {data / 'iocs/bl45p-ea-ioc-01'}")


def test_deploy_local(mock_run, data, ioc):
    mock_run.set_response(ioc.checks[:1] + ioc.deploy_local)
    mock_run.run_cli(f"ioc deploy-local {data / 'iocs/bl45p-ea-ioc-01'}")


def test_deploy(mock_run, data, ioc):
    mock_run.set_response(ioc.checks + ioc.deploy)
    mock_run.run_cli("ioc deploy bl45p-ea-ioc-01 2.0")


def test_instances(mock_run, ioc):
    mock_run.set_response(ioc.checks + ioc.instances)
    mock_run.run_cli("ioc instances bl45p-ea-ioc-01")
