import json
import os
import tempfile
import time
import urllib
from pathlib import Path
from subprocess import CalledProcessError

import typer

import edge_containers_cli.globals as globals
import edge_containers_cli.shell as shell
from edge_containers_cli.cmds.k8s_commands import check_namespace
from edge_containers_cli.docker import Docker
from edge_containers_cli.git import create_version_map
from edge_containers_cli.logging import log
from edge_containers_cli.utils import cleanup_temp


def url_encode(in_string: str) -> str:
    return urllib.parse.quote(in_string, safe="")  # type: ignore


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


def fetch_service_graph(beamline_repo: str) -> dict:
    version_map = read_cached_dict(url_encode(beamline_repo), globals.IOC_CACHE)
    if not version_map:
        tmp_dir = Path(tempfile.mkdtemp())
        version_map = create_version_map(beamline_repo, tmp_dir)
        cache_dict(url_encode(beamline_repo), globals.IOC_CACHE, version_map)
        cleanup_temp(tmp_dir)

    return version_map


def avail_services(ctx: typer.Context) -> list[str]:
    params = ctx.parent.params  # type: ignore
    services_repo = params["repo"] or globals.EC_SERVICES_REPO

    # This block prevents getting a stack trace during autocompletion
    try:
        services_graph = fetch_service_graph(services_repo)
        return list(services_graph.keys())
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]


def avail_versions(ctx: typer.Context) -> list[str]:
    params = ctx.parent.params  # type: ignore
    beamline_repo = params["repo"] or globals.EC_SERVICES_REPO
    service_name = ctx.params["service_name"]

    # This block prevents getting a stack trace during autocompletion
    try:
        version_map = fetch_service_graph(beamline_repo)
        svc_versions = version_map[service_name]
        return svc_versions
    except KeyError:
        log.error("IOC not found")
        return [" "]
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]


def force_plain_completion() -> list[str]:
    return []


def running_svc(ctx: typer.Context) -> list[str]:
    params = ctx.parent.params  # type: ignore
    namespace = params["namespace"] or globals.EC_K8S_NAMESPACE

    # This block prevents getting a stack trace during autocompletion
    try:
        if namespace == globals.LOCAL_NAMESPACE:
            docker = Docker().docker
            format = "{{.Names}}"
            command = f"{docker} ps --filter label=is_IOC=true --format {format}"
            svc_list = str(shell.run_command(command, interactive=False)).split()
            return svc_list
        else:
            check_namespace(namespace)
            columns = "-o custom-columns=IOC_NAME:metadata.labels.app"
            command = f"kubectl -n {namespace} get pod {columns}"
            svc_list = str(shell.run_command(command, interactive=False)).split()[1:]
            return svc_list
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]


def all_svc(ctx: typer.Context) -> list[str]:
    params = ctx.parent.params  # type: ignore
    namespace = params["namespace"] or globals.EC_K8S_NAMESPACE

    # This block prevents getting a stack trace during autocompletion
    try:
        if namespace == globals.LOCAL_NAMESPACE:
            docker = Docker().docker
            format = "{{.Names}}"
            command = f"{docker} ps -a --filter label=is_IOC=true --format {format}"
            svc_list = str(shell.run_command(command, interactive=False)).split()
            return svc_list
        else:
            check_namespace(namespace)
            command = f"helm list -qn {namespace}"
            svc_list = str(shell.run_command(command, interactive=False)).split()
            return svc_list
    except typer.Exit:
        return [" "]
    except CalledProcessError:
        return [" "]
