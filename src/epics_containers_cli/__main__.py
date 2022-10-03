from typing import Optional

import typer

from . import __version__
from .cmd_dev import dev
from .cmd_k8s import k8s
from .logging import init_logging
from .shell import check_tools

__all__ = ["main"]

cli = typer.Typer()

cli.add_typer(dev, name="dev", help="Commands for building and debugging IOCs")
cli.add_typer(k8s, name="k8s", help="Commands for interacting with the cluster")


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


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()
