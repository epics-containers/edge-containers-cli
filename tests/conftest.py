import os
import re
from pathlib import Path
from typing import Dict, List, Union
from types import SimpleNamespace

from mock import patch
from pytest import fixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

from epics_containers_cli.logging import log

os.environ["EC_EPICS_DOMAIN"] = "bl45p"
os.environ["EC_K8S_NAMESPACE"] = "bl45p"
os.environ["EC_GIT_ORG"] = "https://github.com/epics-containers"
os.environ["EC_LOG_URL"] = (
    "https://graylog2.diamond.ac.uk/search?rangetype=relative&fields=message%2C"
    "source&width=1489&highlightMessage=&relative=172800&q=pod_name%3A{ioc_name}*"
)
os.environ["EC_DEBUG"] = "1"
os.environ["EC_CONTAINER_CLI"] = "podman"


class MockRun:
    cmd: str = "cmd"
    rsp: str = "rsp"

    def __init__(self):
        self.cmd_rsp = {}
        self._runner = CliRunner()
        self.log: str = ""

    def _str_command(
        self, command: str, interactive: bool = True, error_OK: bool = False
    ):
        self.log += (
            f"\nCMD: {command}\n    interactive:{interactive}, error_OK:{error_OK}"
        )

        cmd_rsp = self.cmd_rsp.pop(0)
        cmd = cmd_rsp[self.cmd]
        rsp = cmd_rsp[self.rsp]

        self.log += f"\nRET: {rsp}\n"

        matches = re.match(cmd, command)
        assert matches is not None, f"command mismatch: {cmd} != {command}"

        if interactive:
            assert isinstance(rsp, bool), "interactive commands must return bool"
        else:
            assert isinstance(rsp, str), "non-interactive commands must return str"

        return rsp

    def set_response(self, cmd_rsp: List[Dict[str, Union[str, bool]]]):
        self.log = ""
        self.cmd_rsp = cmd_rsp

    def run_cli(self, *args):
        self.log = ""

        result = self._runner.invoke(cli, [str(x) for x in args])
        if result.exception:
            log.error(self.log)
            raise result.exception
        assert result.exit_code == 0, result


MOCKRUN = MockRun()

patcher = patch("epics_containers_cli.shell.run_command", MOCKRUN._str_command)

patcher.start()

# this is imported last so that the patches above are applied
from epics_containers_cli.__main__ import cli  # noqa: E402


@fixture
def mock_run():
    return MOCKRUN


@fixture
def data() -> Path:
    return Path(__file__).parent / "data"


@fixture()
def ioc(data):
    file = Path(__file__).parent / "data" / "ioc.yaml"
    yaml = YAML(typ="safe").load(file)
    return SimpleNamespace(**yaml)
