import webbrowser
from datetime import datetime
from pathlib import Path

import typer

import epics_containers_cli.helm as helm

from .globals import Context
from .shell import EC_LOG_URL, check_domain, check_ioc, run_command

ioc = typer.Typer()


@ioc.command()
def attach(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to attach to"),
):
    """Attach to the IOC shell of a live IOC"""
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    run_command(
        f"kubectl -it -n {domain} attach  deploy/{ioc_name}",
        interactive=True,
    )


@ioc.command()
def delete(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to delete"),
):
    """Remove an IOC helm deployment from the cluster"""
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    if not typer.confirm(
        f"This will remove all versions of {ioc_name} "
        "from the cluster. Are you sure ?"
    ):
        raise typer.Abort()

    run_command(f"helm delete -n {domain} {ioc_name}")


@ioc.command()
def template(
    ctx: typer.Context,
    ioc_path: Path = typer.Argument(..., help="folder of local ioc definition"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    print out the helm template generated from a local ioc instance
    """
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)

    datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")
    domain = c.domain
    check_domain(domain)

    ioc_name = ioc_path.name.lower()

    chart = helm.Helm(domain, ioc_name, args=args, template=True, repo=c.beamline_repo)
    chart.deploy_local(ioc_path)


@ioc.command()
def deploy_local(
    ctx: typer.Context,
    ioc_path: Path = typer.Argument(
        ..., help="root folder of local helm chart to deploy"
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """Deploy a local IOC helm chart directly to the cluster with dated beta version"""
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)

    ioc_name = ioc_path.name.lower()

    chart = helm.Helm(domain, ioc_name, args=args)
    chart.deploy_local(ioc_path, yes)


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
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)

    chart = helm.Helm(domain, ioc_name, args, version, repo=c.beamline_repo)
    chart.deploy()


@ioc.command()
def instances(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to inspect"),
):
    """List all versions of the IOC available in the helm registry"""
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)

    chart = helm.Helm(domain, ioc_name, repo=c.beamline_repo)
    chart.versions()


@ioc.command()
def exec(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to run in"),
):
    """Execute a bash prompt in a live IOC's container"""
    c: Context = ctx.obj
    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    run_command(f"kubectl -it -n {domain} exec  deploy/{ioc_name} -- bash")


@ioc.command()
def log_history(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to inspect",
    ),
):
    """Open historical logs for an IOC"""

    if EC_LOG_URL is None:
        typer.echo("K8S_LOG_URL environment not set")
        raise typer.Exit(1)

    url = EC_LOG_URL.format(ioc_name=ioc_name)
    webbrowser.open(url)


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
    c: Context = ctx.obj

    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    previous = "-p" if prev else ""
    fol = "-f" if follow else ""

    run_command(f"kubectl -n {domain} logs deploy/{ioc_name} {previous} {fol}")


@ioc.command()
def restart(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to restart"),
):
    """Restart an IOC"""
    c: Context = ctx.obj

    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    pod_name = run_command(f"kubectl get -n {domain} pod -l app={ioc_name} -o name")
    run_command(f"kubectl delete -n {domain} {pod_name}")


@ioc.command()
def start(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to start"),
):
    """Start an IOC"""
    c: Context = ctx.obj

    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    run_command(f"kubectl scale -n {domain} deploy --replicas=1 {ioc_name}")


@ioc.command()
def stop(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to stop"),
):
    """Stop an IOC"""
    c: Context = ctx.obj

    domain = c.domain
    check_domain(domain)
    check_ioc(ioc_name, domain)

    run_command(f"kubectl scale -n {domain} deploy --replicas=0 {ioc_name}")
