import json
import os
import time
from pathlib import Path
from tempfile import mkdtemp

import typer

from epics_containers_cli.git import create_ioc_graph
from epics_containers_cli.globals import (
    CACHE_EXPIRY,
    CACHE_FOLDER,
    IOC_CACHE,
)


def cache_dict(cached_file: str, data_struc: dict):
    if not os.path.exists(CACHE_FOLDER):
        os.makedirs(CACHE_FOLDER)

    cache_path = os.path.join(CACHE_FOLDER, cached_file)
    with open(cache_path, "w") as f:
        f.write(json.dumps(data_struc, indent=4))


def read_cached_dict(cached_file: str) -> dict:
    cache_path = os.path.join(CACHE_FOLDER, cached_file)
    read_dict = {}

    # Check cache if available
    if os.path.exists(cache_path):
        # Read from cache if not stale
        if (time.time() - os.path.getmtime(cache_path)) < CACHE_EXPIRY:
            with open(cache_path) as f:
                read_dict = json.load(f)

    return read_dict


def fetch_ioc_graph(beamline_repo):
    ioc_graph = read_cached_dict(IOC_CACHE)
    if not ioc_graph:
        ioc_graph = create_ioc_graph(beamline_repo, Path(mkdtemp()))
        cache_dict(IOC_CACHE, ioc_graph)

    return ioc_graph


def avail_IOCs(ctx: typer.Context):
    # remove os.environment call when ctx.obj.beamline_repo set upfront
    beamline_repo = os.environ.get("EC_DOMAIN_REPO", "")
    ioc_graph = fetch_ioc_graph(beamline_repo)
    return list(ioc_graph.keys())


def avail_versions(ctx: typer.Context):
    # remove os.environment call when ctx.obj.beamline_repo set upfront
    beamline_repo = os.environ.get("EC_DOMAIN_REPO", "")
    ioc_name = ctx.params["ioc_name"]
    ioc_graph = fetch_ioc_graph(beamline_repo)

    return ioc_graph[ioc_name]
