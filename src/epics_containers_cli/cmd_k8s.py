from typing import Optional

import typer

from .logging import log
from .shell import check_helm

k8s = typer.Typer()  # for first level sub commands


@k8s.callback()
def k8s_main(
    beamline: Optional[str] = typer.Option(
        "bl45p",
        "-b",
        "--beamline",
        help="Beamline cluster to use",
    ),
):
    """Cluster sub-commands"""


@k8s.command()
def attach(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to attach to",
    ),
):
    """Attach to the IOC shell of a live IOC"""
    log.info("attaching to %s", ioc_name)


@k8s.command()
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
        None,
        help="Helm repo to pull from",
    ),
):
    """Pulls an IOC helm chart and deploys it to the cluster"""
    check_helm(helm_registry)
    log.info("deploying %s, version %s", ioc_name, version)
