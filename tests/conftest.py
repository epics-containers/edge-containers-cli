import os
import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, List, Union

from mock import patch
from pytest import fixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

os.environ["EC_K8S_NAMESPACE"] = "bl45p"
os.environ["EC_DOMAIN_REPO"] = "https://github.com/epics-containers/bl45p"
os.environ["EC_LOG_URL"] = (
    "https://graylog2.diamond.ac.uk/search?rangetype=relative&fields=message%2C"
    "source&width=1489&highlightMessage=&relative=172800&q=pod_name%3A{ioc_name}*"
)
os.environ["EC_DEBUG"] = "1"

TMPDIR = Path("/tmp/ec_tests")
DATA_PATH = Path(__file__).parent / "data"


class MockRun:
    """
    A Class to mock the shell.run_command function. As the primary function
    of all ec commands mocking this lets us test the majority of functionality
    in isolation.

    IMPORTANT: to debug these tests - just run pytest from the command line.
    When there are failed tests they will dump the sequence of calls to
    run_command and the expected response. You can then copy and paste the
    command back into the test YAML in the tests/data to fix the test.
    (after verifying that it is and expected command!)
    """

    cmd = "cmd"
    rsp = "rsp"

    def __init__(self) -> None:
        self.cmd_rsp: List[Dict] = []
        self._runner = CliRunner()
        self.log: str = ""
        self.params: List[str] = []

    def _str_command(
        self, command: str, interactive: bool = True, error_OK: bool = False
    ):
        """
        A function to replace shell.run_command that verifies the command
        against the expected sequence of commands and returns the test
        response.
        """
        self.log += f"\n\nFNC: ec {' '.join(self.params)}"
        self.log += f"\nCMD: {command}"

        cmd_rsp = self.cmd_rsp.pop(0)
        cmd = cmd_rsp[self.cmd].format(data=DATA_PATH)
        rsp = cmd_rsp[self.rsp]

        self.log += f"\nTST: {cmd}"
        self.log += f"\nARG: interactive:{interactive}, error_OK:{error_OK}"
        self.log += f"\nRET: {rsp}\n"

        # try a raw match first then use the test value as a regex
        if cmd != command:
            matches = re.match(cmd, command)
            assert matches is not None, f"command mismatch: {cmd} != {command}"

        if interactive:
            assert isinstance(rsp, bool), "interactive commands must return bool"
        else:
            assert isinstance(rsp, str), "non-interactive commands must return str"

        return rsp

    def set_seq(self, cmd_rsp: List[Dict[str, Union[str, bool]]]):
        """
        Set up the expected sequence of commands that we expect to see come
        through the mock of run_command. Also supplies the response to
        return for each command. The structure of the list is as per the
        YAML files used in the tests e.g. tests/data/ioc.yaml
        """
        shutil.rmtree(TMPDIR, ignore_errors=True)
        self.log = ""
        self.cmd_rsp = cmd_rsp

    def call(self, func: Callable, *args, **kwargs):
        """
        Call a function and report the sequence of commands / repsponses when
        an error occurs.
        """
        self.params = [func.__name__]

        try:
            result = func(*args, **kwargs)
        except Exception:
            log.error(self.log)
            raise

        return result

    def run_cli(self, args: str):
        """
        Call a typer CLI function and report the sequence of commands /
        repsponses when an error occurs.
        """
        self.params = [str(x) for x in args.split(" ")]

        result = self._runner.invoke(cli, self.params)
        if result.exception:
            log.error(self.log)
            raise result.exception

        if len(self.cmd_rsp) > 0:
            log.error(self.log)
            raise AssertionError("not all commands were run")


MOCKRUN = MockRun()


def mktempdir(_1=None, _2=None, _3=None):
    TMPDIR.mkdir(parents=True, exist_ok=True)
    return str(TMPDIR)


patch("epics_containers_cli.shell.run_command", MOCKRUN._str_command).start()
patch("typer.confirm", return_value=True).start()
patch("tempfile.mkdtemp", mktempdir).start()
patch("webbrowser.open", MOCKRUN._str_command).start()


# import project code last so that the patches above are applied
from epics_containers_cli.__main__ import cli  # noqa: E402
from epics_containers_cli.logging import log  # noqa: E402


@fixture
def mock_run():
    return MOCKRUN


@fixture
def data() -> Path:
    return DATA_PATH


@fixture()
def ioc(data):
    file = Path(__file__).parent / "data" / "ioc.yaml"
    yaml = YAML(typ="safe").load(file)
    return SimpleNamespace(**yaml)


@fixture()
def local(data):
    file = Path(__file__).parent / "data" / "local.yaml"
    os.environ["EC_K8S_NAMESPACE"] = "local"
    yaml = YAML(typ="safe").load(file)
    return SimpleNamespace(**yaml)


@fixture()
def dev(data):
    file = Path(__file__).parent / "data" / "dev.yaml"
    yaml = YAML(typ="safe").load(file)
    return SimpleNamespace(**yaml)
