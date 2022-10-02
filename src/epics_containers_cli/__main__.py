from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .command import check_helm, check_tools
from .logging import init_logging, log

__all__ = ["main"]

cli = typer.Typer()  # for first level sub commands
dev = typer.Typer()  # for nested sub commands of 'dev'
cli.add_typer(
    dev, name="dev", help="Sub-commands for building and debugging IOCs"
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
        help="log.info the version of ibek and exit",
    ),
    log_level: str = typer.Option(
        "WARN", help="log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""
    init_logging(log_level)
    check_tools()


@dev.command()
def launch(
    folder: Path = typer.Option(Path("."), help="generic IOC container project folder"),
    config: Optional[Path] = typer.Option(None, help="IOC instance config folder"),
    start: bool = typer.Option(True, help="IOC instance config folder"),
):
    """Launch a generic IOC container"""
    log.info(
        "launching generic IOC in %s with config %s (starting = %s)",
        folder,
        config,
        start,
    )


@dev.command()
def build(
    folder: Path = typer.Option(Path("."), help="IOC project folder"),
):
    """Build a generic IOC container image"""
    log.info("building %s", folder)


@dev.command()
def debug_build():
    """Launches a container with the most recent image build.
    Useful for debugging failed builds"""
    log.info("debugging last build")


@cli.command()
def deploy(
    ioc_name: str = typer.Argument(..., help="Name of the IOC to deploy"),
    version: str = typer.Argument(..., help="Version tag of the IOC to deploy"),
    helm_registry: Optional[str] = typer.Option(None, help="Helm repo to pull from"),
):
    """Pulls an IOC helm chart and deploys it to the cluster"""
    check_helm(helm_registry)
    log.info("deploying %s, version %s", ioc_name, version)


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()
