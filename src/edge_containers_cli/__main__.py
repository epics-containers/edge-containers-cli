from typing import Optional

import typer

import edge_containers_cli.globals as globals
from edge_containers_cli.cmds.cli import cli

from . import __version__
from .logging import init_logging

__all__ = ["main"]


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@cli.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Log the version of ec and exit",
    ),
    repo: str = typer.Option(
        "",
        "-r",
        "--repo",
        help="service/ioc instances repository",
    ),
    namespace: str = typer.Option(
        "", "-n", "--namespace", help="kubernetes namespace to use"
    ),
    log_level: str = typer.Option(
        "WARN", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    verbose: bool = typer.Option(
        globals.EC_VERBOSE, "-v", "--verbose", help="print the commands we run"
    ),
    debug: bool = typer.Option(
        globals.EC_DEBUG,
        "-d",
        "--debug",
        help="Enable debug logging to console and retain temporary files",
    ),
):
    """Edge Containers assistant CLI"""

    globals.EC_VERBOSE, globals.EC_DEBUG = bool(verbose), bool(debug)

    init_logging(log_level.upper())

    # create a context dictionary to pass to all sub commands
    repo = repo or globals.EC_SERVICES_REPO
    namespace = namespace or globals.EC_K8S_NAMESPACE
    ctx.ensure_object(globals.Context)
    context = globals.Context(namespace=namespace, beamline_repo=repo)
    ctx.obj = context


# test with:
#     python -m edge_containers_cli
if __name__ == "__main__":
    cli()
