import urllib
from pathlib import Path

import typer

import edge_containers_cli.globals as globals
from edge_containers_cli.backend import backend as ec_backend
from edge_containers_cli.cmds.commands import CommandError
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.git import GitError, create_version_map
from edge_containers_cli.shell import ShellError
from edge_containers_cli.utils import cache_dict, new_workdir, read_cached_dict


def url_encode(in_string: str) -> str:
    return urllib.parse.quote(in_string, safe="")  # type: ignore


def autocomplete_backend_init(ctx: typer.Context):
    params = ctx.parent.params  # type: ignore
    context = ECContext(
        repo=params["repo"],
        target=params["target"],
        log_url=params["log_url"],
    )
    ec_backend.set_context(context)


def fetch_service_graph(repo: str) -> dict:
    version_map = read_cached_dict(
        globals.CACHE_ROOT / url_encode(repo), globals.SERVICE_CACHE
    )
    if not version_map:
        with new_workdir() as path:
            version_map = create_version_map(
                repo,
                Path(globals.SERVICES_DIR),
                path,
                shared_files=[globals.SHARED_VALUES],
            )
            cache_dict(
                globals.CACHE_ROOT / url_encode(repo),
                globals.SERVICE_CACHE,
                version_map,
            )

    return version_map


def avail_services(ctx: typer.Context) -> list[str]:
    autocomplete_backend_init(ctx)

    # This block prevents getting a stack trace during autocompletion
    try:
        services_graph = fetch_service_graph(ec_backend.commands.repo)
        return list(services_graph.keys())
    except (ShellError, CommandError) as e:
        typer.echo(f"\n{e}", nl=False, err=True)
        return []


def avail_versions(ctx: typer.Context) -> list[str]:
    autocomplete_backend_init(ctx)
    service_name = ctx.params["service_name"]

    # This block prevents getting a stack trace during autocompletion
    try:
        version_map = fetch_service_graph(ec_backend.commands.repo)
        svc_versions = version_map[service_name]
        return svc_versions
    except KeyError:
        typer.echo(f"\n{service_name} not found", nl=False, err=True)
        return []
    except (ShellError, CommandError, GitError) as e:
        typer.echo(f"\n{e}", nl=False, err=True)
        return []


def force_plain_completion() -> list[str]:
    """Forces filepath completion"""
    return []


def running_svc(ctx: typer.Context) -> list[str]:
    autocomplete_backend_init(ctx)
    try:
        return ec_backend.commands._running_services()  # noqa: SLF001
    except (CommandError, ShellError) as e:
        typer.echo(f"\n{e}", nl=False, err=True)
        return []


def all_svc(ctx: typer.Context) -> list[str]:
    autocomplete_backend_init(ctx)
    try:
        return ec_backend.commands._all_services()  # noqa: SLF001
    except (CommandError, ShellError) as e:
        typer.echo(f"\n{e}", nl=False, err=True)
        return []
