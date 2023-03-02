from typing import Optional

import typer

from . import __version__
from .cmd_dev import dev
from .cmd_ioc import ioc
from .context import Context
from .kubectl import fmt_deploys, fmt_pods, fmt_pods_wide
from .logging import init_logging
from .shell import K8S_BEAMLINE, K8S_HELM_REGISTRY, K8S_IMAGE_REGISTRY, run_command

__all__ = ["main"]


cli = typer.Typer()
cli.add_typer(dev, name="dev", help="Commands for building, debugging containers")
cli.add_typer(ioc, name="ioc", help="Commands for managing IOCs in the cluster")


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
        help="Log the version of ec and exit",
    ),
    beamline: str = typer.Option(
        K8S_BEAMLINE,
        "-b",
        "--beamline",
        help="Beamline namespace to use",
    ),
    image_registry: str = typer.Option(
        K8S_IMAGE_REGISTRY, help="Image registry to pull from"
    ),
    helm_registry: str = typer.Option(
        K8S_HELM_REGISTRY, help="Helm registry to pull from"
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress printing of commands executed",
    ),
    log_level: str = typer.Option(
        "WARN", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""
    init_logging(log_level.upper())

    if beamline is None:
        print("Please set K8S_BEAMLINE or pass --beamline")
        raise typer.Exit(1)
    if helm_registry is None:
        print("Please set K8S_HELM_REGISTRY or pass --helm-registry")
        raise typer.Exit(1)
    if image_registry is None:
        print("Please set K8S_IMAGE_REGISTRY or pass --image-registry")
        raise typer.Exit(1)

    # create a context dictionary to pass to all sub commands
    ctx.ensure_object(Context)
    context = Context(beamline, helm_registry, image_registry, not quiet)
    ctx.obj = context


@cli.command()
def ps(
    ctx: typer.Context,
    all: bool = typer.Option(
        False, "-a", "--all", help="list stopped IOCs as well as running IOCs"
    ),
    wide: bool = typer.Option(False, help="use a wide format with additional fields"),
):
    """List the IOCs running in the current domain"""

    bl = ctx.obj.beamline

    if all:
        run_command(
            f"kubectl -n {bl} get deploy -l is_ioc==True -o {fmt_deploys}", show=True
        )
    else:
        format = fmt_pods_wide if wide else fmt_pods
        run_command(f"kubectl -n {bl} get pod -l is_ioc==True -o {format}", show=True)


@cli.command()
def resources(ctx: typer.Context):
    """Output information about a domain's cluster resources"""

    bl = ctx.obj.beamline

    print("\nDeployments")
    print(
        run_command(f"kubectl get -n {bl} deployment -l beamline={bl} -o {fmt_deploys}")
    )
    print("\nPods")
    print(run_command(f"kubectl get -n {bl} pod -l beamline={bl} -o {fmt_pods}"))
    print("\nconfigMaps")
    print(run_command(f"kubectl get -n {bl} configmap -l beamline={bl}"))
    print("\nPersistent Volume Claims")
    print(run_command(f"kubectl get -n {bl} pvc -l beamline={bl}"))


@cli.command()
def monitor(ctx: typer.Context):
    """Monitor the status of iocs in a domain"""
    print("Not yet implemented - will be a rich text resizable terminal UI")

    # TODO


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    print("HELLO")
    cli()
