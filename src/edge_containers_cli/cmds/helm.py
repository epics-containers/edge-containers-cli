import tempfile
from pathlib import Path
from typing import Optional

import typer
from ruamel.yaml import YAML

import edge_containers_cli.globals as globals
import edge_containers_cli.shell as shell
from edge_containers_cli.utils import (
    chdir,
    check_instance_path,
    cleanup_temp,
    local_version,
    log,
)


class Helm:
    """
    A class for handling helm operations
    """

    def __init__(
        self,
        namespace: str,
        service_name: str,
        args: str = "",
        version: Optional[str] = None,
        template: bool = False,
        repo: Optional[str] = None,
    ):
        """
        Create a helm chart from a local or a remote repo
        """
        self.service_name = service_name
        self.beamline_repo = repo
        self.namespace = namespace
        self.args = args
        self.version = version or local_version()
        self.template = template

        self.tmp = Path(tempfile.mkdtemp())

    def __del__(self):
        if hasattr(self, "tmp"):
            cleanup_temp(self.tmp)

    def deploy_local(self, service_path: Path, yes: bool = False):
        """
        Deploy a local helm chart directly to the cluster with dated beta version
        """

        service_name, service_path = check_instance_path(service_path)

        if not yes and not self.template:
            typer.echo(
                f"Deploy {service_name} TEMPORARY version {self.version} "
                f"from {service_path} to domain {self.namespace}"
            )
            if not typer.confirm("Are you sure ?"):
                raise typer.Abort()

        self._do_deploy(service_path)

    def deploy(self):
        """
        Generate an IOC helm chart and deploy it to the cluster
        """
        if not self.version:
            log.error("Version not found")
            raise typer.Exit(1)

        shell.run_command(
            f"git clone {self.beamline_repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={self.version}",
            interactive=False,
        )

        self._do_deploy(self.tmp / "services" / self.service_name)

    def _do_deploy(self, service_folder: Path):
        """
        Generate an on the fly chart using beamline chart with config folder.
        Deploy the resulting helm chart to the cluster.
        """

        chart_paths = list(service_folder.glob(f"{globals.SHARED_CHARTS_FOLDER}/*"))

        # package up the charts to get the appVersion set
        for chart in chart_paths:
            shell.run_command(f"helm dependency update {chart}", interactive=False)

        with chdir(service_folder):
            shell.run_command(
                f"helm package {service_folder} -u --app-version {self.version}",
                interactive=False,
            )

            # Determine package name
            with open("Chart.yaml") as fp:
                chart_yaml = YAML(typ="safe").load(fp)
            package_path = (
                service_folder / f'{chart_yaml["name"]}-{chart_yaml["version"]}.tgz'
            )

        # use helm to install the chart
        self._install(package_path)

    def _install(self, helm_chart: Path):
        """
        Execute helm install command
        """

        helm_cmd = "template" if self.template else "upgrade --install"
        # complicated stderr filter to suppress helm symlink warnings
        cmd = (
            f"bash -c "
            f'"'
            f"helm {helm_cmd} {self.service_name} {helm_chart} "
            f"--namespace {self.namespace} {self.args}"
            f" 2> >(grep -v 'found symbolic link' >&2) "
            f'"'
        )

        output = shell.run_command(cmd, interactive=False)
        typer.echo(output)
