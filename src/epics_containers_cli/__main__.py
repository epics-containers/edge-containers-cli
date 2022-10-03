from typing import Optional

import typer

from . import __version__
from .cmd_dev import dev
from .kubectl import fmt_deploys, fmt_pods
from .logging import init_logging, log
from .shell import (
    K8S_BEAMLINE,
    K8S_HELM_REGISTRY,
    check_beamline,
    check_helm,
    check_ioc,
    check_kubectl,
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
    log_level: str = typer.Option(
        "WARN", help="log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""
    init_logging(log_level)

    # create a context dictionary to pass to all sub commands
    # TODO review this - better to have our own dataclass for context
    ctx.ensure_object(dict)
    ctx.obj["beamline"] = check_beamline(beamline)


@cli.command()
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

    run_command(
        f"kubectl -it -n {bl} attach  deploy/{ioc_name}",
        show=True,
        interactive=True,
    )


@cli.command()
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


@cli.command()
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


@cli.command()
def info(ctx: typer.Context):
    """output information about beamline cluster resources"""

    bl = ctx.obj["beamline"]
    log.info("beamline info for %s", bl)

    print("\nDeployments")
    print(run_command(f"kubectl get deployment -l beamline={bl} -o {fmt_deploys}"))
    print("\nPods")
    print(run_command(f"kubectl get pod -l beamline={bl} -o {fmt_pods}"))
    print("\nconfigMaps")
    print(run_command(f"kubectl get configmap -l beamline={bl}"))
    print("\nPeristent Volume Claims")
    print(run_command(f"kubectl get pvc -l beamline={bl}"))


@cli.command()
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
    """lists all versions of the IOC available in the helm registry"""

    log.info("getting versions for %s", ioc_name)
    registry = check_helm(helm_registry)

    run_command(
        f"podman run --rm quay.io/skopeo/stable "
        f"list-tags docker://{registry}/{ioc_name}",
        show=True,
    )


@cli.command()
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

    run_command(
        f"kubectl -it -n {bl} exec  deploy/{ioc_name} -- bash",
        show=True,
        interactive=True,
    )
