import typer

from .kubectl import fmt_deploys, fmt_pods, fmt_pods_wide
from .shell import run_command

bl = typer.Typer()


@bl.command()
def info(ctx: typer.Context):
    """Output information about a beamline's cluster resources"""

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


@bl.command()
def ps(
    ctx: typer.Context,
    all: bool = typer.Option(
        False, "-a", "--all", help="list stopped IOCs as well as running IOCs"
    ),
    wide: bool = typer.Option(False, help="use a wide format with additional fields"),
):
    """List the IOCs running on a beamline"""

    bl = ctx.obj.beamline

    if all:
        run_command(
            f"kubectl -n {bl} get deploy -l is_ioc==True -o {fmt_deploys}", show=True
        )
    else:
        format = fmt_pods_wide if wide else fmt_pods
        run_command(f"kubectl -n {bl} get pod -l is_ioc==True -o {format}", show=True)


@bl.command()
def monitor(ctx: typer.Context):
    """Monitor the status of iocs on a beamline"""
    print("Not yet implemented - will be a rich text resizable terminal UI")

    # TODO
