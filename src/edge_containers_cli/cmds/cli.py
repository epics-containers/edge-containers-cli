import tempfile
from pathlib import Path

import polars
import typer
from natsort import natsorted

import edge_containers_cli.globals as globals
from edge_containers_cli.autocomplete import (
    all_svc,
    avail_services,
    avail_versions,
    force_plain_completion,
    running_svc,
)
from edge_containers_cli.cmds.k8s_commands import K8sCommands
from edge_containers_cli.cmds.local_commands import LocalCommands
from edge_containers_cli.git import create_svc_graph
from edge_containers_cli.logging import log
from edge_containers_cli.utils import cleanup_temp, drop_path

cli = typer.Typer(pretty_exceptions_show_locals=False)


@cli.command()
def ps(
    ctx: typer.Context,
    all: bool = typer.Option(
        False, "-a", "--all", help="list stopped IOCs/services as well as running ones"
    ),
    wide: bool = typer.Option(
        False, "--wide", "-w", help="use a wide format with additional fields"
    ),
):
    """List the IOCs/services running in the current namespace"""
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj).ps(all, wide)
    else:
        K8sCommands(ctx.obj).ps(all, wide)


@cli.command()
def env(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="show all relevant environment variables"
    ),
):
    """List all relevant environment variables"""
    LocalCommands(ctx.obj).environment(verbose == verbose)


@cli.command()
def attach(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the IOC/service to attach to", autocompletion=running_svc
    ),
):
    """
    Attach to the console of a live service
    """
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).attach()
    else:
        K8sCommands(ctx.obj, service_name).attach()


@cli.command()
def delete(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the IOC/service to delete", autocompletion=all_svc
    ),
):
    """
    Remove a helm deployment from the cluster
    """
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).delete()
    else:
        K8sCommands(ctx.obj, service_name).delete()


@cli.command()
def template(
    ctx: typer.Context,
    svc_instance: Path = typer.Argument(
        ...,
        help="folder of local service definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
    ),  # noqa: B008
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    print out the helm template generated from a local service instance
    """
    args = f"{args} --debug"
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        typer.echo("Not applicable to local deployments")
    else:
        K8sCommands(ctx.obj).template(svc_instance, args)


@cli.command()
def deploy_local(
    ctx: typer.Context,
    svc_instance: Path = typer.Argument(
        ...,
        help="folder of local service definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    Deploy a local IOC/service helm chart directly to the cluster with dated beta version
    """
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj).deploy_local(svc_instance, yes, args)
    else:
        K8sCommands(ctx.obj).deploy_local(svc_instance, yes, args)


@cli.command()
def deploy(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the IOC/service to deploy", autocompletion=avail_services
    ),
    version: str = typer.Argument(
        ...,
        help="Version tag of the IOC/service to deploy",
        autocompletion=avail_versions,
    ),
    args: str = typer.Option(
        "", help="Additional args for helm or docker, 'must be quoted'"
    ),
):
    """
    Pull an IOC/service helm chart version from the domain repo and deploy it to the cluster
    """
    service_name = drop_path(service_name)
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).deploy(service_name, version, args)
    else:
        K8sCommands(ctx.obj, service_name, check=False).deploy(
            service_name, version, args
        )


@cli.command()
def list(
    ctx: typer.Context,
):
    """List all IOCs/services available in the helm registry"""
    tmp_dir = Path(tempfile.mkdtemp())
    svc_graph = create_svc_graph(ctx.obj.beamline_repo, tmp_dir)
    svc_list = natsorted(svc_graph.keys())
    log.debug(f"svc_graph = {svc_graph}")

    versions = [natsorted(svc_graph[svc])[-1] for svc in svc_list]
    services_df = polars.from_dict({"name": svc_list, "version": versions})
    print(services_df)

    cleanup_temp(tmp_dir)


@cli.command()
def instances(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the IOC/service to inspect", autocompletion=avail_services
    ),
):
    """List all versions of the IOC/service available in the helm registry"""
    tmp_dir = Path(tempfile.mkdtemp())
    svc_graph = create_svc_graph(ctx.obj.beamline_repo, tmp_dir)
    try:
        svc_list = svc_graph[service_name]
    except KeyError:
        svc_list = []

    sorted_list = natsorted(svc_list)[::-1]
    services_df = polars.from_dict({"version": sorted_list})
    print(services_df)

    cleanup_temp(tmp_dir)


@cli.command()
def exec(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ...,
        help="Name of the IOC/service container to run in",
        autocompletion=running_svc,
    ),
):
    """Execute a bash prompt in a running container"""
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).exec()
    else:
        K8sCommands(ctx.obj, service_name).exec()


@cli.command()
def log_history(
    service_name: str = typer.Argument(
        ...,
        help="Name of the IOC/service to inspect",
        autocompletion=all_svc,
    ),
):
    """Open historical logs for an IOC/service"""
    K8sCommands(None, service_name).log_history()


@cli.command()
def logs(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the IOC/service to inspect", autocompletion=running_svc
    ),
    prev: bool = typer.Option(
        False,
        "--previous",
        "-p",
        help="Show log from the previous instance of the IOC/service",
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow the log stream"),
):
    """Show logs for current and previous instances of an IOC/service"""
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).logs(prev, follow)
    else:
        K8sCommands(ctx.obj, service_name).logs(prev, follow)


@cli.command()
def restart(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the container to restart", autocompletion=running_svc
    ),
):
    """Restart an IOC/service"""
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).restart()
    else:
        K8sCommands(ctx.obj, service_name).restart()


@cli.command()
def start(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ..., help="Name of the IOC/service container to start", autocompletion=all_svc
    ),
):
    """Start an IOC/service"""
    log.debug("Starting IOC/service with LOCAL={ctx.obj.namespace == " "}")
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).start()
    else:
        K8sCommands(ctx.obj, service_name).start()


@cli.command()
def stop(
    ctx: typer.Context,
    service_name: str = typer.Argument(
        ...,
        help="Name of the IOC/service container to stop",
        autocompletion=running_svc,
    ),
):
    """Stop an IOC/service"""
    if ctx.obj.namespace == globals.LOCAL_NAMESPACE:
        LocalCommands(ctx.obj, service_name).stop()
    else:
        K8sCommands(ctx.obj, service_name).stop()


@cli.command()
def validate(
    ctx: typer.Context,
    svc_instance: Path = typer.Argument(
        ...,
        help="folder of local IOC/service definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
    ),
):
    """
    Verify a local IOC definition folder is valid

    Does not work for non-IOC services.

    Checks that values.yaml points at a valid image
    Checks that ioc.yaml has the matching schema header and that it passes
      scheme validation
    """
    LocalCommands(ctx.obj).validate_instance(svc_instance)
