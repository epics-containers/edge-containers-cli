from pathlib import Path
from tempfile import mkdtemp

import typer

from epics_containers_cli.git import create_ioc_graph
from epics_containers_cli.globals import LOCAL_NAMESPACE
from epics_containers_cli.ioc.ioc_autocomplete import (
    all_iocs,
    avail_IOCs,
    avail_versions,
    force_plain_completion,
    running_iocs,
)
from epics_containers_cli.ioc.k8s_commands import IocK8sCommands
from epics_containers_cli.ioc.local_commands import IocLocalCommands
from epics_containers_cli.logging import log
from epics_containers_cli.utils import drop_ioc_path

ioc = typer.Typer()


@ioc.command()
def attach(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC to attach to", autocompletion=running_iocs
    ),
):
    """
    Attach to the IOC shell of a live IOC
    """
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).attach()
    else:
        IocK8sCommands(ctx.obj, ioc_name).attach()


@ioc.command()
def delete(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC to delete", autocompletion=all_iocs
    ),
):
    """
    Remove an IOC helm deployment from the cluster
    """
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).delete()
    else:
        IocK8sCommands(ctx.obj, ioc_name).delete()


@ioc.command()
def template(
    ctx: typer.Context,
    ioc_instance: Path = typer.Argument(
        ...,
        help="folder of local ioc definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
    ),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    print out the helm template generated from a local ioc instance
    """
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        typer.echo("Not applicable to local deployments")
    else:
        IocK8sCommands(ctx.obj).template(ioc_instance, args)


@ioc.command()
def deploy_local(
    ctx: typer.Context,
    ioc_instance: Path = typer.Argument(
        ...,
        help="folder of local ioc definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    Deploy a local IOC helm chart directly to the cluster with dated beta version
    """
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj).deploy_local(ioc_instance, yes, args)
    else:
        IocK8sCommands(ctx.obj).deploy_local(ioc_instance, yes, args)


@ioc.command()
def deploy(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC to deploy", autocompletion=avail_IOCs
    ),
    version: str = typer.Argument(
        ..., help="Version tag of the IOC to deploy", autocompletion=avail_versions
    ),
    args: str = typer.Option(
        "", help="Additional args for helm or docker, 'must be quoted'"
    ),
):
    """
    Pull an IOC helm chart version from the domain repo and deploy it to the cluster
    """
    ioc_name = drop_ioc_path(ioc_name)
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).deploy(ioc_name, version, args)
    else:
        IocK8sCommands(ctx.obj, ioc_name).deploy(ioc_name, version, args)


@ioc.command()
def instances(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC to inspect", autocompletion=avail_IOCs
    ),
):
    """List all versions of the IOC available in the helm registry"""
    typer.echo(f"Available instance versions for {ioc_name}:")
    ioc_graph = create_ioc_graph(ctx.obj.beamline_repo, Path(mkdtemp()))
    try:
        iocs_list = ioc_graph[ioc_name]
    except KeyError:
        iocs_list = []
    typer.echo("  ".join(iocs_list))


@ioc.command()
def exec(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC container to run in", autocompletion=running_iocs
    ),
):
    """Execute a bash prompt in a live IOC's container"""
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).exec()
    else:
        IocK8sCommands(ctx.obj, ioc_name).exec()


@ioc.command()
def log_history(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to inspect",
        autocompletion=all_iocs,
    ),
):
    """Open historical logs for an IOC"""
    IocK8sCommands(None, ioc_name).log_history()


@ioc.command()
def logs(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC to inspect", autocompletion=running_iocs
    ),
    prev: bool = typer.Option(
        False, "--previous", "-p", help="Show log from the previous instance of the IOC"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow the log stream"),
):
    """Show logs for current and previous instances of an IOC"""
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).logs(prev, follow)
    else:
        IocK8sCommands(ctx.obj, ioc_name).logs(prev, follow)


@ioc.command()
def restart(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC container to restart", autocompletion=running_iocs
    ),
):
    """Restart an IOC"""
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).restart()
    else:
        IocK8sCommands(ctx.obj, ioc_name).restart()


@ioc.command()
def start(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC container to start", autocompletion=all_iocs
    ),
):
    """Start an IOC"""
    log.debug("Starting IOC with LOCAL={ctx.obj.namespace == " "}")
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).start()
    else:
        IocK8sCommands(ctx.obj, ioc_name).start()


@ioc.command()
def stop(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(
        ..., help="Name of the IOC container to stop", autocompletion=running_iocs
    ),
):
    """Stop an IOC"""
    if ctx.obj.namespace == LOCAL_NAMESPACE:
        IocLocalCommands(ctx.obj, ioc_name).stop()
    else:
        IocK8sCommands(ctx.obj, ioc_name).stop()


@ioc.command()
def validate(
    ctx: typer.Context,
    ioc_instance: Path = typer.Argument(
        ...,
        help="folder of local ioc definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
    ),
):
    """
    Verify a local IOC definition folder is valid

    Checks that values.yaml points at a valid image
    Checks that ioc.yaml has the matching schema header and that it passes
      scheme validation
    """
    IocLocalCommands(ctx.obj).validate_instance(ioc_instance)
