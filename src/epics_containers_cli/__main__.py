from typing import Optional

import typer

from . import __version__
from .cmd_bl import bl
from .cmd_dev import dev
from .cmd_ioc import ioc
from .context import Context
from .logging import init_logging
from .shell import K8S_BEAMLINE, K8S_HELM_REGISTRY, K8S_IMAGE_REGISTRY

__all__ = ["main"]


cli = typer.Typer()
cli.add_typer(dev, name="dev", help="Commands for building, debugging containers")
cli.add_typer(ioc, name="ioc", help="Commands for managing IOCs in the cluster")
cli.add_typer(bl, name="bl", help="Commands for managing beamlines")


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()


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
    beamline: str = typer.Option(
        K8S_BEAMLINE,
        "-b",
        "--beamline",
        help="Beamline namespace to use",
    ),
    image_registry: str = typer.Option(
        K8S_IMAGE_REGISTRY, help="Image registry to pull from"
    ),
    helm_registry: str = typer.Option(
        K8S_HELM_REGISTRY, help="Helm registry to pull from"
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress printing of commands executed",
    ),
    log_level: str = typer.Option(
        "WARN", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""
    init_logging(log_level.upper())

    if beamline is None:
        print("Please set K8S_BEAMLINE or pass --beamline")
        raise typer.Exit(1)
    if helm_registry is None:
        print("Please set K8S_HELM_REGISTRY or pass --helm-registry")
        raise typer.Exit(1)
    if image_registry is None:
        print("Please set K8S_IMAGE_REGISTRY or pass --image-registry")
        raise typer.Exit(1)

    # create a context dictionary to pass to all sub commands
    ctx.ensure_object(Context)
    context = Context(beamline, helm_registry, image_registry, not quiet)
    ctx.obj = context
