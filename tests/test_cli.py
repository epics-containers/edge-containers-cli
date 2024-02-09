import subprocess
import sys

from edge_containers_cli import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "edge_containers_cli", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
