from typing import Optional

import typer

from edge_containers_cli.cli import cli
from edge_containers_cli.definitions import ENV, ECBackends, ECContext, ECLogLevels

from . import __version__
from .backend import backend as ec_backend
from .backend import init_backend
from .logging import init_logging
from .shell import init_shell
from .utils import init_cleanup

__all__ = ["main"]


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def backend_callback(ctx: typer.Context, backend: ECBackends):
    init_backend(backend)
    # Dynamically drop any method not implemented
    not_implemented = [
        mthd.replace("_", "-") for mthd in ec_backend.get_notimplemented()
    ]
    for command in not_implemented:
        typer_commands = ctx.command.commands  # type: ignore
        if command in typer_commands:
            typer_commands.pop(command)

    return backend.value


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
        ECContext().repo,
        "-r",
        "--repo",
        help="Service instances repository",
        envvar=ENV.repo.value,
    ),
    namespace: str = typer.Option(
        ECContext().namespace,
        "-n",
        "--namespace",
        help="Kubernetes namespace to use",
        envvar=ENV.namespace.value,
    ),
    backend: ECBackends = typer.Option(
        ECBackends.K8S,
        "-b",
        "--backend",
        callback=backend_callback,
        is_eager=True,
        help="Backend to use",
        envvar=ENV.backend.value,
        expose_value=True,
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Print the commands we run",
        envvar=ENV.verbose.value,
        show_default=True,
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Print the commands we run without execution",
        envvar=ENV.dryrun.value,
        show_default=True,
    ),
    debug: bool = typer.Option(
        False,
        "-d",
        "--debug",
        help="Enable debug logging, retain temp files",
        envvar=ENV.debug.value,
        show_default=True,
    ),
    log_level: ECLogLevels = typer.Option(
        ECLogLevels.WARNING,
        help="Log level",
        envvar=ENV.log_level.value,
    ),
    log_url: str = typer.Option(
        ECContext().log_url,
        help="Log url",
        envvar=ENV.log_url.value,
    ),
):
    """Edge Containers assistant CLI"""
    init_logging(ECLogLevels.DEBUG if debug else log_level)
    init_shell(verbose, dryrun)
    init_cleanup(debug)

    context = ECContext(
        repo=repo,
        namespace=namespace,
        log_url=log_url,
    )
    ec_backend.set_context(context)

# test with:
#     python -m edge_containers_cli
if __name__ == "__main__":
    cli()