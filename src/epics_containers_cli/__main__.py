import os
from typing import Optional

import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.ioc.k8s_commands import IocK8sCommands
from epics_containers_cli.ioc.local_commands import IocLocalCommands

from . import __version__
from .dev.dev_cli import dev
from .ioc.ioc_cli import ioc
from .k8s.k8s_cli import cluster
from .logging import init_logging

__all__ = ["main"]


cli = typer.Typer(pretty_exceptions_show_locals=False)
cli.add_typer(
    dev,
    name="dev",
    help="Commands for building, debugging containers. See 'ec dev --help'",
)
cli.add_typer(
    ioc,
    name="ioc",
    help="Commands for managing IOCs in the cluster. See 'ec ioc --help'",
)
cli.add_typer(
    cluster,
    name="k8s",
    help="Commands communicating with the k8s cluster. See 'ec cluster --help",
)


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
        help="beamline or accelerator domain repository of ioc instances",
    ),
    namespace: str = typer.Option(
        "", "-n", "--namespace", help="kubernetes namespace to use"
    ),
    log_level: str = typer.Option(
        "WARN", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    verbose: bool = typer.Option(
        glob_vars.EC_VERBOSE, "-v", "--verbose", help="print the commands we run"
    ),
    debug: bool = typer.Option(
        glob_vars.EC_DEBUG, "-d", "--debug", help="Enable debug logging to console"
    ),
):
    """EPICS Containers assistant CLI"""

    glob_vars.EC_VERBOSE, glob_vars.EC_DEBUG = bool(verbose), bool(debug)

    init_logging(log_level.upper())

    # create a context dictionary to pass to all sub commands
    repo = repo or os.environ.get("EC_DOMAIN_REPO", "")
    namespace = namespace or os.environ.get("EC_K8S_NAMESPACE", "")
    ctx.ensure_object(glob_vars.Context)
    context = glob_vars.Context(namespace, repo)
    ctx.obj = context


@cli.command()
def ps(
    ctx: typer.Context,
    all: bool = typer.Option(
        False, "-a", "--all", help="list stopped IOCs as well as running IOCs"
    ),
    wide: bool = typer.Option(
        False, "--wide", "-w", help="use a wide format with additional fields"
    ),
):
    """List the IOCs running in the current namespace"""
    if ctx.obj.namespace == glob_vars.LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj).ps(all, wide)
    else:
        IocK8sCommands(ctx.obj).ps(all, wide)


@cli.command()
def env(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="show all relevant environment variables"
    ),
):
    IocLocalCommands(ctx.obj).environment(verbose == verbose)


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()
