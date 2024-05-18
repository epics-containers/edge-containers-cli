import webbrowser
from pathlib import Path

import polars
import typer

import edge_containers_cli.globals as globals
import edge_containers_cli.shell as shell
from edge_containers_cli.cmds.monitor import MonitorApp
from edge_containers_cli.logging import log


class Commands:
    """
    A base class for K8SCommands and LocalCommands

    Implements the common functionality but defers specialist functions to
    the subclasss

    Allows the CLI or the TUI to call functions without worrying about local
    vs Kubernetes containers
    """

    def __init__(self, ctx: globals.Context):
        self.namespace = ctx.namespace
        self.beamline_repo = ctx.beamline_repo

    def attach(self, service_name):
        raise NotImplementedError

    def delete(self, service_name):
        raise NotImplementedError

    def template(self, svc_instance: Path, args: str):
        raise NotImplementedError

    def deploy_local(self, service_name):
        raise NotImplementedError

    def deploy(self, service_name: str, version: str, args: str):
        raise NotImplementedError

    def exec(self, service_name: str):
        raise NotImplementedError

    def logs(self, service_name: str, prev: bool, follow: bool):
        raise NotImplementedError

    def restart(self, service_name: str):
        raise NotImplementedError

    def start(self, service_name: str):
        raise NotImplementedError

    def stop(self, service_name: str):
        raise NotImplementedError

    def get_services(self, all: bool) -> list:
        raise NotImplementedError

    def ps(self, all: bool, wide: bool):
        select_data = self.get_services(all)
        services_df = polars.DataFrame(select_data)
        if not wide:
            services_df.drop_in_place("image")
        print(services_df)

    def environment(self, verbose: bool):
        """
        declare the environment settings for ec
        """
        ns = self.namespace

        if ns == globals.LOCAL_NAMESPACE:
            typer.echo("ioc commands deploy to the local docker/podman instance")
        else:
            self._check_namespace(ns)
            typer.echo(f"ioc commands deploy to the {ns} namespace the K8S cluster")

        typer.echo("\nEC environment variables:")
        shell.run_command("env | grep '^EC_'", interactive=False, show=True)

    def log_history(self, service_name):
        if not globals.EC_LOG_URL:
            log.error("EC_LOG_URL environment not set")
            raise typer.Exit(1)

        url = globals.EC_LOG_URL.format(service_name=service_name)
        webbrowser.open(url)
