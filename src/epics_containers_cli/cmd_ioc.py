import os
import webbrowser
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import typer

from .context import Context
from .shell import (
    K8S_HELM_ROOT,
    K8S_LOG_URL,
    check_domain,
    check_ioc,
    get_helm_chart,
    run_command,
)

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
        show_cmd=c.show_cmd,
        interactive=True,
    )


@ioc.command()
def delete(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to delete"),
):
    """Remove an IOC helm deployment from the cluster"""
    c: Context = ctx.obj

    bl = c.domain
    check_domain(bl)
    check_ioc(ioc_name, bl)

    if not typer.confirm(
        f"This will remove all versions of {ioc_name} "
        "from the cluster. Are you sure ?"
    ):
        raise typer.Abort()

    run_command(
        f"helm delete -n {bl} {ioc_name}",
        show=True,
        show_cmd=c.show_cmd,
    )


@ioc.command()
def template(
    ctx: typer.Context,
    ioc_path: Path = typer.Argument(
        ..., help="root folder of local helm chart to deploy"
    ),
):
    """print out the helm template generated from a local ioc helm chart"""
    c: Context = ctx.obj

    version = datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")
    domain = c.domain
    check_domain(domain)

    ioc_name, _ = get_helm_chart(ioc_path)
    ioc_path = ioc_path.absolute()

    with TemporaryDirectory() as temp:
        os.chdir(temp)
        run_command(
            f"helm package -u {ioc_path} --version {version} --app-version {version}",
            show=True,
            show_cmd=c.show_cmd,
        )
        package = list(Path(".").glob("*.tgz"))[0]
        run_command(
            f"helm template --debug -n {domain} {ioc_name} {package}",
            show=True,
            show_cmd=c.show_cmd,
        )


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

    version = datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")
    domain = c.domain
    check_domain(domain)

    ioc_name, _ = get_helm_chart(ioc_path)
    ioc_path = ioc_path.absolute()

    if not yes:
        print(
            f"Deploy {ioc_name} TEMPORARY version {version} "
            f"from {ioc_path} to domain {domain}"
        )
        if not typer.confirm("Are you sure ?"):
            raise typer.Abort()

    with TemporaryDirectory() as temp:
        os.chdir(temp)
        run_command(
            f"helm package -u {ioc_path} --version {version} --app-version {version}",
            show=True,
            show_cmd=c.show_cmd,
        )
        package = list(Path(".").glob("*.tgz"))[0]
        run_command(
            f"helm upgrade -n {domain} --install {ioc_name} {args} {package}",
            show=True,
            show_cmd=c.show_cmd,
        )


@ioc.command()
def deploy(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to deploy"),
    version: str = typer.Argument(..., help="Version tag of the IOC to deploy"),
    helm_folder: str = typer.Option("", help="Override the extra level of helm path"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """Pull an IOC helm chart and deploy it to the cluster"""
    c: Context = ctx.obj

    bl = c.domain
    check_domain(bl)

    helm_path = ctx.obj.helm_registry
    if helm_folder != "":
        helm_path = f"{K8S_HELM_ROOT}/{helm_folder}"

    run_command(
        f"helm upgrade -n {bl} --install {ioc_name} {args} "
        f"oci://{helm_path}/{ioc_name} --version {version}",
        show=True,
        show_cmd=c.show_cmd,
    )


@ioc.command()
def exec(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to run in"),
):
    """Execute a bash prompt in a live IOC's container"""
    c: Context = ctx.obj

    bl = c.domain
    check_domain(bl)
    check_ioc(ioc_name, bl)

    run_command(
        f"kubectl -it -n {bl} exec  deploy/{ioc_name} -- bash",
        show=True,
        interactive=True,
        show_cmd=c.show_cmd,
    )


@ioc.command()
def log_history(
    ioc_name: str = typer.Argument(
        ...,
        help="Name of the IOC to inspect",
    ),
):
    """Open historical logs for an IOC"""

    if K8S_LOG_URL is None:
        print("K8S_LOG_URL environment not set")
        raise typer.Exit(1)

    url = K8S_LOG_URL.format(ioc_name=ioc_name)
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

    bl = c.domain
    check_domain(bl)
    check_ioc(ioc_name, bl)

    previous = "-p" if prev else ""
    fol = "-f" if follow else ""

    run_command(
        f"kubectl -n {bl} logs deploy/{ioc_name} {previous} {fol}",
        show=True,
        show_cmd=c.show_cmd,
        interactive=True,
    )


@ioc.command()
def restart(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to restart"),
):
    """Restart an IOC"""
    c: Context = ctx.obj

    bl = c.domain
    check_domain(bl)
    check_ioc(ioc_name, bl)

    pod_name = run_command(f"kubectl get -n {bl} pod -l app={ioc_name} -o name")
    run_command(
        f"kubectl delete -n {bl} {pod_name}",
        show=True,
        show_cmd=c.show_cmd,
    )


@ioc.command()
def start(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to start"),
):
    """Start an IOC"""
    c: Context = ctx.obj

    bl = c.domain
    check_domain(bl)
    check_ioc(ioc_name, bl)

    run_command(
        f"kubectl scale -n {bl} deploy --replicas=1 {ioc_name}",
        show=True,
        show_cmd=c.show_cmd,
    )


@ioc.command()
def stop(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC container to stop"),
):
    """Stop an IOC"""
    c: Context = ctx.obj

    bl = c.domain
    check_domain(bl)
    check_ioc(ioc_name, bl)

    run_command(
        f"kubectl scale -n {bl} deploy --replicas=0 {ioc_name}",
        show=True,
        show_cmd=c.show_cmd,
    )


@ioc.command()
def versions(
    ctx: typer.Context,
    ioc_name: str = typer.Argument(..., help="Name of the IOC to inspect"),
):
    """List all versions of the IOC available in the helm registry"""
    c: Context = ctx.obj

    run_command(
        f"podman run --rm quay.io/skopeo/stable "
        f"list-tags docker://{c.helm_registry}/{ioc_name}",
        show=True,
        show_cmd=c.show_cmd,
    )
