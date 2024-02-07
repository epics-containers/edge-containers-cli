# Some tests that really run the underlying commands:
# requires podman to be installed
from pathlib import Path

from typer.testing import CliRunner

from epics_containers_cli.__main__ import cli
from epics_containers_cli.utils import chdir

THIS_DIR = Path(__file__).parent


def test_validate():
    """Test the validate command"""
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "validate",
            f"{THIS_DIR}/data/iocs/bl45p-ea-ioc-01",
        ],
    )

    assert result.exit_code == 0


def test_validate_chdir():
    """Test the validate command from a different directory"""
    runner = CliRunner()

    with chdir(THIS_DIR / "data/beamline-chart"):
        result = runner.invoke(
            cli,
            [
                "validate",
                f"{THIS_DIR}/data/iocs/bl45p-ea-ioc-01",
            ],
        )

    assert result.exit_code == 0
