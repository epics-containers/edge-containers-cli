import typer

from .kubectl import fmt_deploys, fmt_pods
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
