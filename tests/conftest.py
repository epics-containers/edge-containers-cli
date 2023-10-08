import os
from pathlib import Path
from typing import List, Union

from mock import patch
from pytest import fixture
from typer.testing import CliRunner

from epics_containers_cli.logging import log

os.environ["EC_EPICS_DOMAIN"] = "test"
os.environ["EC_DEBUG"] = "1"


class MockRun:
    def __init__(self):
        self.response: Union[List[Union[bool, str]], Union[bool, str]] = True
        self._runner = CliRunner()
        self.log: str = ""

    def _str_command(
        self, command: str, interactive: bool = True, error_OK: bool = False
    ):
        self.log += (
            f"\nCMD: {command}\n    interactive:{interactive}, error_OK:{error_OK}"
        )

        if isinstance(self.response, List):
            response = self.response.pop()
        else:
            response = self.response

        self.log += f"\nRET: {response}\n"

        if interactive:
            assert isinstance(response, bool)
        else:
            assert isinstance(response, str)

        return response

    def set_response(self, *response):
        self.log = ""
        self.response = list(response)

    def run_cli(self, *args):
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
def templates():
    return Path(__file__).parent.parent / "src" / "ibek" / "templates"


@fixture
def samples():
    return Path(__file__).parent / "samples"
