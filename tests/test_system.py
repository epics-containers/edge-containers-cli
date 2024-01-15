# Some tests that really run the underlying commands:
# requires podman to be installed
import os
from pathlib import Path

from typer.testing import CliRunner

from epics_containers_cli.__main__ import cli

THIS_DIR = Path(__file__).parent


def test_validate():
    """Test the validate command"""
    runner = CliRunner()
    # TODO: changing "." to "" below reproduces bug
    #   https://github.com/epics-containers/epics-containers-cli/issues/74
    os.chdir(".")

    runner.invoke(
        cli,
        [
            "ioc",
            "validate",
            "data/iocs/bl45p-ea-ioc-01",
        ],
    )
