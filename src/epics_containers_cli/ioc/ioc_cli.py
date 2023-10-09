from pathlib import Path

import typer

from epics_containers_cli.ioc.ioc_commands import IocCommands

ioc = typer.Typer()


@ioc.command()
def attach(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to attach to"),
):
    """
    Attach to the IOC shell of a live IOC
    """
    IocCommands(ctx.obj, ioc_name).attach()


@ioc.command()
def delete(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to delete"),
):
    """
    Remove an IOC helm deployment from the cluster
    """
    IocCommands(ctx.obj, ioc_name).delete()


@ioc.command()
def template(
    ctx: typer.Context,
    ioc_instance: Path = typer.Argument(..., help="folder of local ioc definition"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    print out the helm template generated from a local ioc instance
    """
    IocCommands(ctx.obj).template(ioc_instance, args)


@ioc.command()
def deploy_local(
    ctx: typer.Context,
    ioc_instance: Path = typer.Argument(..., help="folder of local ioc definition"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    Deploy a local IOC helm chart directly to the cluster with dated beta version
    """
    IocCommands(ctx.obj).deploy_local(ioc_instance, yes, args)


@ioc.command()
def deploy(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to deploy"),
    version: str = typer.Argument(..., help="Version tag of the IOC to deploy"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    Pull an IOC helm chart version from the domain repo and deploy it to the cluster
    """
    IocCommands(ctx.obj, ioc_name).deploy(ioc_name, version, args)


@ioc.command()
def instances(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to inspect"),
):
    """List all versions of the IOC available in the helm registry"""
    IocCommands(ctx.obj, ioc_name).instances()


@ioc.command()
def exec(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to run in"),
):
    """Execute a bash prompt in a live IOC's container"""
    IocCommands(ctx.obj, ioc_name).exec()


@ioc.command()
def log_history(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to inspect",
    ),
):
    """Open historical logs for an IOC"""
    IocCommands(None, ioc_name).log_history()


@ioc.command()
def logs(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to inspect"),
    prev: bool = typer.Option(
        False, "--previous", "-p", help="Show log from the previous instance of the IOC"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow the log stream"),
):
    """Show logs for current and previous instances of an IOC"""
    IocCommands(ctx.obj, ioc_name).logs(prev, follow)


@ioc.command()
def restart(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to restart"),
):
    """Restart an IOC"""
    IocCommands(ctx.obj, ioc_name).restart()


@ioc.command()
def start(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to start"),
):
    """Start an IOC"""
    IocCommands(ctx.obj, ioc_name).start()


@ioc.command()
def stop(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to stop"),
):
    """Stop an IOC"""
    IocCommands(ctx.obj, ioc_name).stop()
