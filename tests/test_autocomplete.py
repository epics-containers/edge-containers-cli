"""
IMPORTANT: to debug these tests with pytest from the command line
as specfifed from conftest.py, the general exception handling block
of the tested function must be surpressed
"""

import shutil

from epics_containers_cli.autocomplete import (
    all_iocs,
    avail_IOCs,
    avail_versions,
    running_iocs,
)
from tests.conftest import TMPDIR


def test_all_iocs(mock_run, autocomplete, ctx):
    mock_run.set_seq(autocomplete.all_iocs)

    ctx.parent.parent.params["namespace"] = ""  # use env variable
    result = mock_run.call(all_iocs, ctx)
    assert result == ["bl45p-ea-ioc-01"]


def test_avail_IOCs(mock_run, data, autocomplete, ctx):
    mock_run.set_seq(autocomplete.avail_IOCs)
    shutil.copytree(data / "iocs", TMPDIR / "iocs")

    ctx.parent.parent.params["repo"] = ""  # use env variable
    result = mock_run.call(avail_IOCs, ctx)
    assert result == ["bl45p-ea-ioc-01"]


def test_avail_versions(mock_run, data, autocomplete, ctx):
    mock_run.set_seq(autocomplete.avail_versions)
    # shutil.copytree(data / "iocs", TMPDIR / "iocs") already exists

    ctx.parent.parent.params["repo"] = ""  # use env variable
    ctx.parent.parent.params["ioc_name"] = "bl45p-ea-ioc-01"
    result = mock_run.call(avail_versions, ctx)
    assert result == ["2.0"]


def test_running_iocs(mock_run, autocomplete, ctx):
    mock_run.set_seq(autocomplete.running_iocs)

    ctx.parent.parent.params["namespace"] = ""  # use env variable
    result = mock_run.call(running_iocs, ctx)
    assert result == ["bl45p-ea-ioc-01"]
