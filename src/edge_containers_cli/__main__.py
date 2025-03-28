import os
import sys
from typing import Optional

import typer

from edge_containers_cli.cli import cli, drop_methods, drop_options, set_optional
from edge_containers_cli.definitions import ENV, ECBackends, ECContext, ECLogLevels

from . import __version__
from .backend import backend as ec_backend
from .backend import init_backend
from .logging import init_logging
from .shell import init_shell
from .utils import init_cleanup

__all__ = ["main"]

DEFAULT_BACKEND = ECBackends.ARGOCD


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def backend_callback(ctx: typer.Context, backend: ECBackends):
    init_backend(backend)
    drop_methods(ctx, ec_backend.get_notimplemented_cmds())
    drop_options(ctx, ec_backend.get_notimplemented_params())
    set_optional(ctx, ec_backend.get_optional_params())
    return backend.value


@cli.callback()
def _main(
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
    target: str = typer.Option(
        ECContext().target,
        "-t",
        "--target",
        help="K8S namespace or ARGOCD app-namespace/root-app",
        envvar=ENV.target.value,
    ),
    backend: ECBackends = typer.Option(
        DEFAULT_BACKEND,
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
        target=target,
        log_url=log_url,
    )
    ec_backend.set_context(context)


def force_backend_callback():
    """
    Typer does not execute option callbacks before running --help unless the
    option is explicitly provided
    """
    if "--help" in sys.argv:
        if "-b" not in sys.argv:
            backend = os.environ.get("EC_CLI_BACKEND", DEFAULT_BACKEND)
            sys.argv.insert(1, backend)
            sys.argv.insert(1, "-b")


def main():
    force_backend_callback()
    cli()


# test with:
#     python -m edge_containers_cli
if __name__ == "__main__":
    main()
