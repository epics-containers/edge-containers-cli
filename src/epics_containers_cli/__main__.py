import logging
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .command import check_helm, check_tools

__all__ = ["main"]
log = logging.getLogger(__name__)

cli = typer.Typer()  # for first level sub commands
dev = typer.Typer()  # for nested sub commands of 'dev'
cli.add_typer(
    dev, name="dev", help="sub commands for building and debugging IOCs"
)  # add the nested sub commands to the cli level


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@cli.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Print the version of ibek and exit",
    )
):
    """EPICS Containers assistant CLI"""
    check_tools()


@dev.command()
def launch(
    folder: Path = typer.Option(Path("."), help="ioc project folder"),
):
    """Launch a generic ioc container"""
    print("launching", folder)


@dev.command()
def build(
    folder: Path = typer.Option(Path("."), help="ioc project folder"),
):
    """Build a generic IOC container image"""
    print("building", folder)


@cli.command()
def deploy(
    ioc_name: str = typer.Argument(..., help="Name of the IOC to deploy"),
    version: str = typer.Argument(..., help="Version tag of the IOC to deploy"),
    helm_registry: Optional[str] = typer.Option(None, help="Helm repo to pull from"),
):
    """Pulls an IOC helm chart and invokes helm upgrade"""
    check_helm(helm_registry)
    print("deploying", ioc_name, version)


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()
