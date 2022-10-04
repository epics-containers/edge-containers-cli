import typer

from .kubectl import fmt_deploys, fmt_pods, fmt_pods_wide
from .logging import log
from .shell import run_command

bl = typer.Typer()


@bl.command()
def info(ctx: typer.Context):
    """Output information about a beamline's cluster resources"""

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


@bl.command()
def ps(
    ctx: typer.Context,
    all: bool = typer.Option(
        False, "-a", "--all", help="list stopped IOCs as well as running IOCs"
    ),
    wide: bool = typer.Option(False, help="use a wide format with additional fields"),
):
    """list the IOCs running on a beamline"""

    bl = ctx.obj.beamline
    log.info("ps for beamline %s", bl)

    if all:
        run_command(
            f"kubectl -n {bl} get deploy -l is_ioc==True -o {fmt_deploys}",
            show=True,
            show_cmd=ctx.obj.show_cmd,
        )
    else:
        format = fmt_pods_wide if wide else fmt_pods
        run_command(
            f"kubectl -n {bl} get pod -l is_ioc==True -o {format}",
            show=True,
            show_cmd=ctx.obj.show_cmd,
        )


@bl.command()
def monitor(ctx: typer.Context):
    """Monitor the status of iocs on a beamline"""
    print("Not yet implemented - will be a rich text resizable terminal UI")
