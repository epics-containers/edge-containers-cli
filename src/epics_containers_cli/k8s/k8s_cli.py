import typer

from epics_containers_cli.k8s.k8s_commands import K8sCommands

cluster = typer.Typer()


@cluster.command()
def resources(ctx: typer.Context):
    """Output information about a domain's cluster resources"""
    K8sCommands(ctx.obj).resources()


@cluster.command()
def monitor(ctx: typer.Context):
    """Monitor the status of IOCs in a domain"""
    typer.echo("Not yet implemented - will be a rich text resizable terminal UI")

    # TODO
