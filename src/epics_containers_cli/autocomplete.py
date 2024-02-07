import json
import os
import tempfile
import time
import urllib
from pathlib import Path
from subprocess import CalledProcessError
from typing import List

import typer

import epics_containers_cli.globals as globals
import epics_containers_cli.shell as shell
from epics_containers_cli.docker import Docker
from epics_containers_cli.git import create_ioc_graph
from epics_containers_cli.ioc.k8s_commands import check_namespace
from epics_containers_cli.logging import log
from epics_containers_cli.utils import cleanup_temp


def url_encode(in_string: str) -> str:
    return urllib.parse.quote(in_string, safe="")


def cache_dict(cache_folder: str, cached_file: str, data_struc: dict) -> None:
    cache_dir = os.path.join(globals.CACHE_ROOT, cache_folder)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    cache_path = os.path.join(cache_dir, cached_file)
    with open(cache_path, "w") as f:
        f.write(json.dumps(data_struc, indent=4))


def read_cached_dict(cache_folder: str, cached_file: str) -> dict:
    cache_path = os.path.join(globals.CACHE_ROOT, cache_folder, cached_file)
    read_dict = {}

    # Check cache if available
    if os.path.exists(cache_path):
        # Read from cache if not stale
        if (time.time() - os.path.getmtime(cache_path)) < globals.CACHE_EXPIRY:
            with open(cache_path) as f:
                read_dict = json.load(f)

    return read_dict


def fetch_ioc_graph(beamline_repo: str) -> dict:
    ioc_graph = read_cached_dict(url_encode(beamline_repo), globals.IOC_CACHE)
    if not ioc_graph:
        tmp_dir = Path(tempfile.mkdtemp())
        ioc_graph = create_ioc_graph(beamline_repo, tmp_dir)
        cache_dict(url_encode(beamline_repo), globals.IOC_CACHE, ioc_graph)
        cleanup_temp(tmp_dir)

    return ioc_graph


def avail_IOCs(ctx: typer.Context) -> List[str]:
    params = ctx.parent.parent.params  # type: ignore
    beamline_repo = params["repo"] or globals.EC_SERVICES_REPO

    # This block prevents getting a stack trace during autocompletion
    try:
        ioc_graph = fetch_ioc_graph(beamline_repo)
        return list(ioc_graph.keys())
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]


def avail_versions(ctx: typer.Context) -> List[str]:
    params = ctx.parent.parent.params  # type: ignore
    beamline_repo = params["repo"] or globals.EC_SERVICES_REPO
    ioc_name = ctx.params["ioc_name"]

    # This block prevents getting a stack trace during autocompletion
    try:
        ioc_graph = fetch_ioc_graph(beamline_repo)
        ioc_versions = ioc_graph[ioc_name]
        return ioc_versions
    except KeyError:
        log.error("IOC not found")
        return [" "]
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]


def force_plain_completion() -> List[str]:
    return []


def running_iocs(ctx: typer.Context) -> List[str]:
    params = ctx.parent.parent.params  # type: ignore
    namespace = params["namespace"] or globals.EC_K8S_NAMESPACE

    # This block prevents getting a stack trace during autocompletion
    try:
        if namespace == globals.LOCAL_NAMESPACE:
            docker = Docker().docker
            format = "{{.Names}}"
            command = f"{docker} ps --filter label=is_IOC=true --format {format}"
            ioc_list = str(shell.run_command(command, interactive=False)).split()
            return ioc_list
        else:
            check_namespace(namespace)
            columns = "-o custom-columns=IOC_NAME:metadata.labels.app"
            command = f"kubectl -n {namespace} get pod -l is_ioc==true {columns}"
            ioc_list = str(shell.run_command(command, interactive=False)).split()[1:]
            return ioc_list
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]


def all_iocs(ctx: typer.Context) -> List[str]:
    params = ctx.parent.parent.params  # type: ignore
    namespace = params["namespace"] or globals.EC_K8S_NAMESPACE

    # This block prevents getting a stack trace during autocompletion
    try:
        if namespace == globals.LOCAL_NAMESPACE:
            docker = Docker().docker
            format = "{{.Names}}"
            command = f"{docker} ps -a --filter label=is_IOC=true --format {format}"
            ioc_list = str(shell.run_command(command, interactive=False)).split()
            return ioc_list
        else:
            check_namespace(namespace)
            columns = "-o custom-columns=DEPLOYMENT:metadata.labels.app"
            command = (
                f"kubectl -n {namespace} get statefulset -l is_ioc==true {columns}"
            )
            ioc_list = str(shell.run_command(command, interactive=False)).split()[1:]
            return ioc_list
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]
