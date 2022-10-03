from typing import Optional

import typer

from . import __version__
from .cmd_dev import dev
from .logging import init_logging, log
from .shell import (
    K8S_BEAMLINE,
    K8S_HELM_REGISTRY,
    check_beamline,
    check_helm,
    check_ioc,
    run_command,
)

__all__ = ["main"]

cli = typer.Typer()

cli.add_typer(dev, name="dev", help="Commands for building and debugging IOCs")


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
    log_level: str = typer.Option(
        "WARN", help="log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""
    init_logging(log_level)
    check_beamline(beamline)


@cli.command()
def attach(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to attach to",
    ),
):
    """Attach to the IOC shell of a live IOC"""
    log.info("attaching to %s", ioc_name)


@cli.command()
def deploy(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to deploy",
    ),
    version: str = typer.Argument(
        ...,
        help="Version tag of the IOC to deploy",
    ),
    helm_registry: Optional[str] = typer.Option(
        K8S_HELM_REGISTRY,
        help="Helm registry to pull from",
    ),
):
    """Pulls an IOC helm chart and deploys it to the cluster"""
    check_helm(helm_registry)
    check_ioc(ioc_name)
    log.info("deploying %s, version %s", ioc_name, version)

    run_command(
        f"helm upgrade -n {K8S_BEAMLINE} --install {ioc_name} "
        f"oci://{helm_registry}/{ioc_name} --version {version}",
        show=True,
    )
