# Some tests that really run the underlying commands:
# requires podman to be installed
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from edge_containers_cli.__main__ import cli
from edge_containers_cli.utils import chdir

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
    os.getenv("REMOTE_CONTAINERS") == "true",
    reason="podman tests not supported inside devcontainer",
)
def test_validate_chdir():
    """Test the validate command from a different directory"""
    runner = CliRunner()

    with chdir(THIS_DIR / "data/example-ibek-config"):
        result = runner.invoke(
            cli,
            [
                "validate",
                f"{THIS_DIR}/data/services/bl45p-ea-ioc-01",
            ],
        )

    assert result.exit_code == 0
