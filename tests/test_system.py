# Some tests that really run the underlying commands:
# requires podman to be installed
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from edge_containers_cli.__main__ import cli

THIS_DIR = Path(__file__).parent


@pytest.mark.skipif(
    os.getenv("REMOTE_CONTAINERS") == "true",
    reason="podman tests not supported inside devcontainer",
)
def test_validate():
    """Test the validate command"""
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "validate",
            f"{THIS_DIR}/data/bl01t/services/bl01t-ea-test-01",
        ],
    )

    assert result.exit_code == 0, result.output


@pytest.mark.skipif(
    os.getenv("EC_INTERACTIVE_TESTING") != "true",
    reason="export EC_INTERACTIVE_TESTING=true",
)
def test_deploy():
    """Test deploy"""
    IOC = "bl01t-ea-test-01"
    runner = CliRunner()

    trigger = runner.invoke(
        cli,
        ["deploy", IOC, "2024.3.1", "--wait"],
    )
    assert trigger.exit_code == 0, trigger.output

    check = runner.invoke(cli, "ps")
    assert IOC in check.output
