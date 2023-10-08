import mock

from tests.conftest import MockRun

cmd = MockRun.cmd
rsp = MockRun.rsp

checks = [
    {
        cmd: "kubectl get namespace bl45p -o name",
        rsp: "namespace/bl45p",
    },
    {
        cmd: "kubectl get -n bl45p deploy/bl45p-ea-ioc-01",
        rsp: "bl45p-ea-ioc-01   1/1     1            1           5d5h",
    },
]


def test_attach(mock_run):
    cmds = [
        {
            cmd: "kubectl -it -n bl45p attach deploy/bl45p-ea-ioc-01",
            rsp: True,
        }
    ]
    mock_run.set_response(checks + cmds)
    mock_run.run_cli("ioc", "attach", "bl45p-ea-ioc-01")


@mock.patch("typer.confirm")
def test_delete(mock_typer, mock_run):
    mock_typer.return_value = True
    cmds = [
        {
            cmd: "helm delete -n bl45p bl45p-ea-ioc-01",
            rsp: True,
        },
    ]
    mock_run.set_response(checks + cmds)
    mock_run.run_cli("ioc", "delete", "bl45p-ea-ioc-01")


@mock.patch("typer.confirm")
def test_template(mock_typer, mock_run, samples):
    mock_typer.return_value = True
    cmds = [
        {
            cmd: "helm delete -n bl45p bl45p-ea-ioc-01",
            rsp: True,
        },
    ]
    mock_run.set_response(checks + cmds)
    mock_run.run_cli("ioc", "template", samples / "bl45p-ea-ioc-01")


def test_instances(mock_run):
    cmds = [
        {
            cmd: "git clone https://github.com/epics-containers/bl45p /tmp/.*",
            rsp: "Cloning into '/tmp/xxxxx'...",
        },
        {
            cmd: "git tag",
            rsp: "2.0\n",
        },
        {
            cmd: r"git diff --name-only 2.0 2.0\^",
            rsp: "2.0\n",
        },
    ]
    mock_run.set_response(checks + cmds)
    mock_run.run_cli("ioc", "instances", "bl45p-ea-ioc-01")
