from pathlib import Path

from epics_containers_cli.shell import get_git_name
from tests.conftest import TMPDIR


def test_get_git_name(mock_run, dev):
    mock_run.set_seq(dev.get_git_name)
    result = mock_run.call(get_git_name)
    assert result == ("git@github.com:epics-containers/bl45p.git", Path("/tmp/bl45p"))


def test_get_git_name_https(mock_run, dev):
    mock_run.set_seq(dev.get_git_name_https)
    result = mock_run.call(get_git_name)
    assert result == (
        "https://github.com/epics-containers/ioc-adsimdetector",
        Path("/tmp/ioc-adsimdetector"),
    )


def test_launch_local_generic(mock_run, dev):
    mock_run.set_seq(dev.checks + dev.get_git_name_https + dev.launch_local_generic)
    root = TMPDIR / "ioc-template"
    root.mkdir(parents=True)
    mock_run.run_cli(f"dev launch-local {root}")


def test_launch(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.launch)
    mock_run.run_cli(f"dev launch {data / 'iocs' / 'bl45p-ea-ioc-01'}")


def test_debug_last(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.debug_last1 + dev.get_git_name + dev.debug_last2)
    mock_run.run_cli("dev debug-last")
