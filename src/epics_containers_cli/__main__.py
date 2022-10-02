from argparse import ArgumentParser
from pathlib import Path

import typer

from . import __version__

__all__ = ["main"]

cli = typer.Typer()  # for first level sub commands
dev = typer.Typer()  # for nested sub commands of 'dev'
cli.add_typer(dev, name="dev")  # add the nested sub commands to the cli level


@cli.callback()
def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(args)


@dev.command()
def launch(
    folder: Path = typer.Option(Path("."), help="git project folder to launch"),
):
    """Launch the ioc defined in the current folder"""
    print("launching", folder)


@dev.command()
def build(
    folder: Path = typer.Option(Path("."), help="git project folder to build"),
):
    """Build the ioc in the current folder"""
    print("building", folder)


@cli.command()
def deploy(
    ioc_name: str = typer.Argument(..., help="Name of the IOC to deploy"),
    ioc_version: str = typer.Argument(..., help="Version tag of the IOC to deploy"),
):
    """Finds the IOC helm chart and invokes helm upgrade"""
    print("deploying", ioc_name, ioc_version)


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()
