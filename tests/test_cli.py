import subprocess

from epics_containers_cli import __version__


def test_cli_version():
    cmd = ["ec", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
