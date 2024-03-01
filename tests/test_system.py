# Some tests that really run the underlying commands:
# requires podman to be installed
import os
import time
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
            f"{THIS_DIR}/data/services/bl45p-ea-ioc-01",
        ],
    )

    assert result.exit_code == 0


@pytest.mark.skipif(
    os.getenv("EC_INTERACTIVE_TESTING") != "true",
    reason="export EC_INTERACTIVE_TESTING=true",
)
def test_deploy():
    """Test deploy"""
    runner = CliRunner()

    trigger = runner.invoke(
        cli,
        [
            "deploy",
            "bl47p-ea-test-01",
            "2024.2.1",
        ],
    )

    assert trigger.exit_code == 0, trigger.output

    time.sleep(3)  # Temporary
    check = runner.invoke(cli, "ps")

    assert "bl01c-ea-test-03" in check.output
