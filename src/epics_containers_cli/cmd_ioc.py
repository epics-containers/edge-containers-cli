import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import ruamel.yaml as yaml
import typer

from .logging import log
from .shell import K8S_HELM_REGISTRY, check_helm, check_ioc, check_kubectl, run_command

ioc = typer.Typer()


@ioc.command()
def attach(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to attach to",
    ),
):
    """Attach to the IOC shell of a live IOC"""

    log.info("attaching to %s", ioc_name)
    check_kubectl()
    bl = ctx.obj["beamline"]
    check_ioc(ioc_name, bl)

    run_command(
        f"kubectl -it -n {bl} attach  deploy/{ioc_name}",
        show=True,
        interactive=True,
    )


@ioc.command()
def delete(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to delete",
    ),
):
    """removes an IOC helm deployment from the cluster"""

    log.info("deleting %s", ioc_name)
    check_helm(local=True)
    bl = ctx.obj["beamline"]
    check_ioc(ioc_name, bl)

    if not typer.confirm(
        f"This will remove all versions of {ioc_name} "
        "from the cluster. Are you sure ?"
    ):
        raise typer.Abort()

    run_command(
        f"helm delete -n {bl} {ioc_name}",
        show=True,
    )


@ioc.command()
def deploy_local(
    ctx: typer.Context,
    ioc_path: Path = typer.Argument(
        ...,
        help="root folder of local helm chart to deploy",
    ),
):
    """Deploys a local IOC helm chart directly to the cluster with dated beta version"""

    version = datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")
    log.info("deploying %s, to temporary version %s", ioc_path, version)
    bl = ctx.obj["beamline"]
    check_helm(local=True)

    # verify this is a helm chart and extract the IOC name from it
    with open(ioc_path / "Chart.yaml", "r") as stream:
        chart = yaml.safe_load(stream)

    ioc_name = chart["name"]
    ioc_path = ioc_path.absolute()

    print(
        f"Deploy {ioc_name} TEMPORARY version {version} "
        f"from {ioc_path} to beamline {bl}"
    )
    if not typer.confirm("Are you sure ?"):
        raise typer.Abort()

    with TemporaryDirectory() as temp:
        os.chdir(temp)
        run_command(
            f"helm package -u {ioc_path} --version {version} --app-version {version}",
            show=True,
        )
        run_command(f"helm upgrade --install {ioc_name} *.tgz", show=True)


@ioc.command()
def deploy(
    ctx: typer.Context,
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

    log.info("deploying %s, version %s", ioc_name, version)
    registry = check_helm(helm_registry)
    bl = ctx.obj["beamline"]
    check_ioc(ioc_name, bl)

    run_command(
        f"helm upgrade -n {bl} --install {ioc_name} "
        f"oci://{registry}/{ioc_name} --version {version}",
        show=True,
    )


@ioc.command()
def exec(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC container to run in",
    ),
):
    """Execute a bash prompt in a live IOC's container"""

    log.info("execing bash in %s", ioc_name)
    check_kubectl()
    bl = ctx.obj["beamline"]
    check_ioc(ioc_name, bl)

    run_command(
        f"kubectl -it -n {bl} exec  deploy/{ioc_name} -- bash",
        show=True,
        interactive=True,
    )


@ioc.command()
def versions(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to inspect",
    ),
    helm_registry: Optional[str] = typer.Option(
        K8S_HELM_REGISTRY,
        help="Helm registry to pull from",
    ),
):
    """List all versions of the IOC available in the helm registry"""

    log.info("getting versions for %s", ioc_name)
    registry = check_helm(helm_registry)

    run_command(
        f"podman run --rm quay.io/skopeo/stable "
        f"list-tags docker://{registry}/{ioc_name}",
        show=True,
    )
