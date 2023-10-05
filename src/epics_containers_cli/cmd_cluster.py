import typer

from .kubectl import fmt_deploys, fmt_pods
from .shell import run_command

cluster = typer.Typer()


@cluster.command()
def resources(ctx: typer.Context):
    """Output information about a domain's cluster resources"""

    domain = ctx.obj.domain

    typer.echo("\nDeployments")
    typer.echo(
        run_command(
            f"kubectl get -n {domain} deployment -l beamline={domain} -o {fmt_deploys}"
        )
    )
    typer.echo("\nPods")
    typer.echo(
        run_command(f"kubectl get -n {domain} pod -l beamline={domain} -o {fmt_pods}")
    )
    typer.echo("\nconfigMaps")
    typer.echo(run_command(f"kubectl get -n {domain} configmap -l beamline={domain}"))
    typer.echo("\nPersistent Volume Claims")
    typer.echo(run_command(f"kubectl get -n {domain} pvc -l beamline={domain}"))


@cluster.command()
def monitor(ctx: typer.Context):
    """Monitor the status of IOCs in a domain"""
    typer.echo("Not yet implemented - will be a rich text resizable terminal UI")

    # TODO
