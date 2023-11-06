from pathlib import Path

from epics_containers_cli.git import get_git_name
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


def test_launch_dit(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.launch_dit)
    mock_run.run_cli(f"dev launch {data / 'iocs' / 'bl45p-ea-ioc-01'} --args '-dit'")


def test_debug_last(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.debug_last1 + dev.get_git_name + dev.debug_last2)
    mock_run.run_cli("dev debug-last")


def test_versions(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.get_git_name + dev.versions)
    mock_run.run_cli(f"dev versions {data / 'iocs' / 'bl45p-ea-ioc-01'}")
    mock_run.set_seq(dev.checks + dev.get_git_name_gitlab + dev.versions_gitlab)
    mock_run.run_cli(f"dev versions {data / 'iocs' / 'bl45p-ea-ioc-01'}")


def test_stop(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.stop)
    mock_run.run_cli("dev stop")


def test_exec(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.exec)
    mock_run.run_cli("dev exec")


def test_wait_pv(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.wait_pv)
    mock_run.run_cli("dev wait-pv BL45P-EA-IOC-01:UPTIME")


def test_build(mock_run, dev, data):
    mock_run.set_seq(dev.checks + dev.get_git_name + dev.build)
    mock_run.run_cli("dev build")
