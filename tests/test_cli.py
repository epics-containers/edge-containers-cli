import subprocess
import sys

from edge_containers_cli import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "edge_containers_cli", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__

# def test_list(mock_run, ioc, data: Path):
#     mock_run.set_seq(ioc.instances)
#     # prep what instances expects to find after it cloned bl01t repo
#     TMPDIR.mkdir()
#     shutil.copytree(data / "bl01t/services", TMPDIR / "services")
#     mock_run.run_cli("list")


# def test_instances(mock_run, ioc, data: Path):
#     mock_run.set_seq(ioc.instances)
#     # prep what instances expects to find after it cloned bl01t repo
#     TMPDIR.mkdir()
#     shutil.copytree(data / "bl01t/services", TMPDIR / "services")
#     mock_run.run_cli("instances bl01t-ea-test-01")
