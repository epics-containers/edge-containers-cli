import typer

from .kubectl import fmt_deploys, fmt_pods
from .shell import run_command

cluster = typer.Typer()


@cluster.command()
def resources(ctx: typer.Context):
    """Output information about a domain's cluster resources"""

    bl = ctx.obj.domain

    typer.echo("\nDeployments")
    typer.echo(
        run_command(f"kubectl get -n {bl} deployment -l beamline={bl} -o {fmt_deploys}")
    )
    typer.echo("\nPods")
    typer.echo(run_command(f"kubectl get -n {bl} pod -l beamline={bl} -o {fmt_pods}"))
    typer.echo("\nconfigMaps")
    typer.echo(run_command(f"kubectl get -n {bl} configmap -l beamline={bl}"))
    typer.echo("\nPersistent Volume Claims")
    typer.echo(run_command(f"kubectl get -n {bl} pvc -l beamline={bl}"))


@cluster.command()
def monitor(ctx: typer.Context):
    """Monitor the status of IOCs in a domain"""
    typer.echo("Not yet implemented - will be a rich text resizable terminal UI")

    # TODO
