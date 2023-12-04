import json
import urllib
import os
import time
from pathlib import Path
from tempfile import mkdtemp

import typer

from epics_containers_cli.git import create_ioc_graph
from epics_containers_cli.globals import (
    CACHE_EXPIRY,
    CACHE_ROOT,
    IOC_CACHE,
)


def url_encode(in_string: str):
    return urllib.parse.quote(in_string, safe="")


def cache_dict(cache_folder: str, cached_file: str, data_struc: dict):
    cache_dir = os.path.join(CACHE_ROOT, cache_folder)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    cache_path = os.path.join(cache_dir, cached_file)
    with open(cache_path, "w") as f:
        f.write(json.dumps(data_struc, indent=4))


def read_cached_dict(cache_folder: str, cached_file: str) -> dict:
    cache_path = os.path.join(CACHE_ROOT, cache_folder, cached_file)
    read_dict = {}

    # Check cache if available
    if os.path.exists(cache_path):
        # Read from cache if not stale
        if (time.time() - os.path.getmtime(cache_path)) < CACHE_EXPIRY:
            with open(cache_path) as f:
                read_dict = json.load(f)

    return read_dict


def fetch_ioc_graph(beamline_repo):
    ioc_graph = read_cached_dict(url_encode(beamline_repo), IOC_CACHE)
    if not ioc_graph:
        ioc_graph = create_ioc_graph(beamline_repo, Path(mkdtemp()))
        cache_dict(url_encode(beamline_repo), IOC_CACHE, ioc_graph)

    return ioc_graph


def avail_IOCs(ctx: typer.Context):
    beamline_repo = ctx.parent.parent.params["repo"] \
        or os.environ.get("EC_DOMAIN_REPO", "")
    ioc_graph = fetch_ioc_graph(beamline_repo)
    return list(ioc_graph.keys())


def avail_versions(ctx: typer.Context):
    beamline_repo = ctx.parent.parent.params["repo"] \
        or os.environ.get("EC_DOMAIN_REPO", "")
    ioc_name = ctx.params["ioc_name"]
    ioc_graph = fetch_ioc_graph(beamline_repo)

    try:
        ioc_version = ioc_graph[ioc_name]
    except KeyError:
        ioc_version = ""

    return ioc_version
