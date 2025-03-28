import os
from pathlib import Path

import typer

import edge_containers_cli.globals as globals
from edge_containers_cli.autocomplete import (
    all_svc,
    avail_services,
    avail_versions,
    force_plain_completion,
    running_svc,
)
from edge_containers_cli.backend import backend
from edge_containers_cli.cmds.commands import CommandError
from edge_containers_cli.definitions import ENV
from edge_containers_cli.git import GitError, list_all, list_instances
from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError


def confirmation(message: str, yes: bool):
    typer.echo(message)
    if not (yes or typer.confirm("Are you sure?")):
        raise typer.Abort()


class ErrorHandlingTyper(typer.Typer):
    def __call__(self, *args, **kwargs):
        try:
            super().__call__(*args, **kwargs)
        except (CommandError, ShellError, GitError) as e:
            log.error(e)
            typer.Exit(1)


cli = ErrorHandlingTyper(pretty_exceptions_show_locals=False)


@cli.command()
def attach(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service to attach to",
        autocompletion=running_svc,
        show_default=False,
    ),
):
    """
    Attach to the console of a live service
    """
    backend.commands.attach(service_name)


@cli.command()
def delete(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service to delete",
        autocompletion=all_svc,
        show_default=False,
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """
    Remove a service from the cluster
    """
    confirmation(
        f"Remove {service_name} from the target `{backend.commands.target}`",
        yes,
    )
    backend.commands.delete(service_name)


@cli.command()
def deploy(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service to deploy",
        autocompletion=avail_services,
        show_default=False,
    ),
    version: str = typer.Argument(
        "latest tag",
        help="Version tag or branch of the service to deploy",
        autocompletion=avail_versions,
        show_default=False,
    ),
    wait: bool = typer.Option(False, "--wait", help="Waits for readiness"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    args: str = typer.Option(
        "", help="Additional args for helm or docker, 'must be quoted'"
    ),
):
    """
    Add a service to the cluster from its source repository
    """

    def confirm_callback(svc_version):
        confirmation(
            f"Deploy {service_name.lower()} "
            f"of version `{svc_version}` to target `{backend.commands.target}`",
            yes,
        )

    args = args if not wait else args + " --wait"
    version = version if version != "latest tag" else ""
    backend.commands.deploy(service_name, version, args, confirm_callback)


@cli.command()
def deploy_local(
    svc_instance: Path = typer.Argument(
        ...,
        help="folder of local service definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
        show_default=False,
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    Add a local service helm chart directly to the cluster with dated beta version
    """

    def confirm_callback(svc_version):
        confirmation(
            f"Deploy local {svc_instance.name.lower()} of version `{svc_version}` "
            f"from {svc_instance} to target `{backend.commands.target}`",
            yes,
        )

    backend.commands.deploy_local(svc_instance, args, confirm_callback)


@cli.command()
def env():
    """List all relevant environment variables"""
    for var in ENV:
        print(f"{var.value}={os.environ.get(var.value, 'Not Defined')}")


@cli.command()
def exec(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service container to run in",
        autocompletion=running_svc,
        show_default=False,
    ),
):
    """Execute a bash prompt in a running container"""
    backend.commands.exec(service_name)


@cli.command()
def instances(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service to inspect",
        autocompletion=avail_services,
        show_default=False,
    ),
):
    """List all versions of the specified service in the repository"""
    print(
        list_instances(
            service_name,
            backend.commands.repo,
            Path(globals.SERVICES_DIR),
            shared_files=[globals.SHARED_VALUES],
        )
    )


@cli.command(name="list")
def _list():
    """List all services available in the service repository"""
    print(
        list_all(
            backend.commands.repo,
            Path(globals.SERVICES_DIR),
            shared_files=[globals.SHARED_VALUES],
        )
    )


@cli.command()
def log_history(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service to inspect",
        autocompletion=all_svc,
        show_default=False,
    ),
):
    """Open historical logs for a service"""
    backend.commands.log_history(service_name)


@cli.command()
def logs(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service to inspect",
        autocompletion=running_svc,
        show_default=False,
    ),
    prev: bool = typer.Option(
        False,
        "--previous",
        "-p",
        help="Show log from the previous instance of the service",
    ),
):
    """Show logs for current and previous instances of a service"""
    backend.commands.logs(service_name, prev)


@cli.command()
def monitor(
    running_only: bool = typer.Option(
        False, "-r", "--running-only", help="list only services that are running"
    ),
):
    """Open monitor TUI"""
    from edge_containers_cli.cmds.monitor import (
        MonitorApp,  # Lazy import for performace
    )

    app = MonitorApp(backend.commands, running_only)
    app.run()


@cli.command()
def ps(
    running_only: bool = typer.Option(
        False, "-r", "--running-only", help="list only services that are running"
    ),
):
    """List the services running in the current target"""
    backend.commands.ps(running_only)


@cli.command()
def restart(
    service_name: str = typer.Argument(
        ...,
        help="Name of the container to restart",
        autocompletion=running_svc,
        show_default=False,
    ),
):
    """Restart a service"""
    backend.commands.restart(service_name)


@cli.command()
def start(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service container to start",
        autocompletion=all_svc,
        show_default=False,
    ),
    commit: bool = typer.Option(False, help="Commits the values to the git repo"),
):
    """Start a service"""
    try:
        backend.commands.start(service_name, commit=commit)
    except GitError as e:
        msg = f"{str(e)} - Commit failed. Try 'ec start <service> --no-commit to set values without updating git"
        raise GitError(msg) from e


@cli.command()
def stop(
    service_name: str = typer.Argument(
        ...,
        help="Name of the service container to stop",
        autocompletion=running_svc,
        show_default=False,
    ),
    commit: bool = typer.Option(False, help="Commits the values to the git repo"),
):
    """Stop a service"""
    try:
        backend.commands.stop(service_name, commit=commit)
    except GitError as e:
        msg = f"{str(e)} - Commit failed. Try ec stop <service> --no-commit to set values without updating git"
        raise GitError(msg) from e


@cli.command()
def template(
    svc_instance: Path = typer.Argument(
        ...,
        help="folder of local service definition",
        exists=True,
        file_okay=False,
        resolve_path=True,
        autocompletion=force_plain_completion,
        show_default=False,
    ),
    args: str = typer.Option("", help="Additional args for helm, 'must be quoted'"),
):
    """
    Print out the helm template generated from a local service instance
    """
    args = f"{args} --debug"
    backend.commands.template(svc_instance, args)


def drop_methods(ctx: typer.Context, to_drop: list[str]):
    """Dynamically drop any method not implemented"""
    not_implemented = [mthd.replace("_", "-") for mthd in to_drop]
    typer_commands = ctx.command.commands  # type: ignore
    for command in not_implemented:
        if command in typer_commands:
            typer_commands.pop(command)


def drop_options(ctx: typer.Context, to_drop: dict[str, list[str]]):
    """Dynamically drop any cli options as specified"""
    typer_commands = ctx.command.commands  # type: ignore
    for cmd_name, drop_params in to_drop.items():
        for i, param in enumerate(typer_commands[cmd_name].params):
            if param.name in drop_params:
                typer_commands[cmd_name].params.pop(i)


def set_optional(ctx: typer.Context, to_set: dict[str, list[str]]):
    """Dynamically set any cli options optional as specified"""
    typer_commands = ctx.command.commands  # type: ignore
    for cmd_name, optional_params in to_set.items():
        for i, param in enumerate(typer_commands[cmd_name].params):
            if param.name in optional_params:
                typer_commands[cmd_name].params[i].required = False
