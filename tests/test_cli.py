import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from edge_containers_cli import __version__
from tests.conftest import TMPDIR


def test_cli_version():
    cmd = [sys.executable, "-m", "edge_containers_cli", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__


def test_list(mock_run, CLI, data: Path):
    expect = (
        "| name             | version |\n"
        "|------------------|---------|\n"
        "| bl01t-ea-test-01 | 4.0     |\n"
        "| bl01t-ea-test-02 | 4.0     |\n"
        "| dls-aravis       | 4.0     |\n"
    )
    mock_run.set_seq(CLI.instances)
    # prep what instances expects to find after it cloned bl01t repo
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    res = mock_run.run_cli("list")

    assert res == expect


@pytest.mark.parametrize("command", ["versions", "instances"])
def test_versions(mock_run, CLI, data: Path, command: str):
    # `instances` is the deprecated name for `versions`
    expect = (
        "| version |\n"  # Stops reformating
        "|---------|\n"
        "| 4.0     |\n"
        "| 1.0     |\n"
    )
    mock_run.set_seq(CLI.instances)
    # prep what versions expects to find after it cloned bl01t repo
    TMPDIR.mkdir()
    shutil.copytree(data / "bl01t-services/services", TMPDIR / "services")
    res = mock_run.run_cli(f"{command} bl01t-ea-test-01")
    assert res == expect
