from typing import Optional

import typer

from . import __version__
from .cmd_bl import bl
from .cmd_dev import dev
from .cmd_ioc import ioc
from .context import Context
from .logging import init_logging
from .shell import K8S_BEAMLINE, K8S_QUIET, check_beamline

__all__ = ["main"]


cli = typer.Typer()
cli.add_typer(dev, name="dev", help="Commands for building and debugging IOCs")
cli.add_typer(ioc, name="ioc", help="Commands managing IOCs in the cluster")
cli.add_typer(bl, name="bl", help="Commands managing beamlines")


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
        help="log the version of ec and exit",
    ),
    beamline: Optional[str] = typer.Option(
        K8S_BEAMLINE,
        "-b",
        "--beamline",
        help="Beamline namespace to use",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress printing of commands executed",
    ),
    log_level: str = typer.Option(
        "WARN", help="log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""
    init_logging(log_level)

    beamline = check_beamline(beamline)
    quiet = quiet or bool(K8S_QUIET)

    # create a context dictionary to pass to all sub commands
    ctx.ensure_object(Context)
    context = Context(beamline, not quiet)
    ctx.obj = context
