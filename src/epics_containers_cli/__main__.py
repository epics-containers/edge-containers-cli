from typing import Optional

import typer

from . import __version__
from .cmd_cluster import cluster
from .cmd_dev import dev
from .cmd_ioc import ioc
from .globals import Context
from .kubectl import fmt_deploys, fmt_pods, fmt_pods_wide
from .logging import init_logging
from .shell import (
    EC_DOMAIN_REPO,
    EC_EPICS_DOMAIN,
    EC_GIT_ORG,
    EC_K8S_NAMESPACE,
    check_domain,
    run_command,
)

__all__ = ["main"]


cli = typer.Typer()
cli.add_typer(
    dev,
    name="dev",
    help="Commands for building, debugging containers. See 'ec dev --help'",
)
cli.add_typer(
    ioc,
    name="ioc",
    help="Commands for managing IOCs in the cluster. See 'ec ioc --help'",
)
cli.add_typer(
    cluster,
    name="cluster",
    help="Commands communicating with the k8s cluster. See 'ec cluster --help",
)


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
    domain: str = typer.Option(
        EC_EPICS_DOMAIN, "-d", "--domain", help="beamline or accelerator domain to use"
    ),
    org: str = typer.Option(
        EC_GIT_ORG,
        "-o",
        "--org",
        help="git remote organisation of domain repos",
    ),
    repo: str = typer.Option(
        EC_DOMAIN_REPO,
        "-r",
        "--repo",
        help="beamline or accelerator domain repository of ioc instances",
    ),
    namespace: str = typer.Option(
        EC_K8S_NAMESPACE, "-n", "--namespace", help="kubernetes namespace to use"
    ),
    log_level: str = typer.Option(
        "WARN", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """EPICS Containers assistant CLI"""

    init_logging(log_level.upper())

    # create a context dictionary to pass to all sub commands
    ctx.ensure_object(Context)
    context = Context(domain, namespace, repo, org)
    ctx.obj = context


@cli.command()
def ps(
    ctx: typer.Context,
    all: bool = typer.Option(
        False, "-a", "--all", help="list stopped IOCs as well as running IOCs"
    ),
    wide: bool = typer.Option(
        False, "--wide", "-w", help="use a wide format with additional fields"
    ),
):
    """List the IOCs running in the current domain"""
    domain = ctx.obj.domain
    check_domain(domain)

    if all:
        run_command(f"kubectl -n {domain} get deploy -l is_ioc==True -o {fmt_deploys}")
    else:
        format = fmt_pods_wide if wide else fmt_pods
        run_command(f"kubectl -n {domain} get pod -l is_ioc==True -o {format}")


# test with:
#     python -m epics_containers_cli
if __name__ == "__main__":
    cli()
