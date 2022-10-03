from pathlib import Path
from typing import Optional

import typer

from .logging import log

dev = typer.Typer()  # for nested sub commands of 'dev'


@dev.command()
def launch(
    folder: Path = typer.Option(
        Path("."),
        help="generic IOC container project folder",
    ),
    config: Optional[Path] = typer.Option(
        None,
        help="IOC instance config folder",
    ),
    start: bool = typer.Option(
        True,
        help="IOC instance config folder",
    ),
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
    folder: Path = typer.Option(
        Path("."),
        help="IOC project folder",
    ),
):
    """Build a generic IOC container image"""
    log.info("building %s", folder)


@dev.command()
def debug_build():
    """Launches a container with the most recent image build.
    Useful for debugging failed builds"""
    log.info("debugging last build")
