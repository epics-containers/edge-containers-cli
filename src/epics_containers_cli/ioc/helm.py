import shutil
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.globals import BEAMLINE_CHART_FOLDER, CONFIG_FOLDER
from epics_containers_cli.shell import run_command
from epics_containers_cli.utils import check_ioc_instance_path, log


class Helm:
    """
    A class for handling helm operations
    """

    def __init__(
        self,
        domain: str,
        ioc_name: str,
        args: str = "",
        version: Optional[str] = None,
        template: bool = False,
        repo: Optional[str] = None,
    ):
        """
        Create a helm chart from a local or a remote repo
        """
        self.ioc_name = ioc_name
        self.beamline_repo = repo
        self.namespace = domain
        self.args = args
        self.version = version or datetime.strftime(
            datetime.now(), "%Y.%-m.%-d-b%-H.%-M"
        )
        self.template = template

        self.tmp = Path(mkdtemp())

        self.bl_chart_folder = self.tmp / BEAMLINE_CHART_FOLDER
        self.bl_chart_path = self.bl_chart_folder / "Chart.yaml"
        self.bl_config_folder = self.bl_chart_folder / CONFIG_FOLDER

        self.ioc_config_folder = self.tmp / "iocs" / str(self.ioc_name) / CONFIG_FOLDER

    def __del__(self):
        # keep the tmp folder if debug is enabled for inspection
        if not glob_vars.EC_DEBUG:
            if hasattr(self, "tmp"):
                shutil.rmtree(self.tmp, ignore_errors=True)

    def deploy_local(self, ioc_path: Path, yes: bool = False):
        """
        Deploy a local IOC helm chart directly to the cluster with dated beta version
        """

        ioc_name, ioc_path = check_ioc_instance_path(ioc_path)

        if not yes and not self.template:
            typer.echo(
                f"Deploy {ioc_name} TEMPORARY version {self.version} "
                f"from {ioc_path} to domain {self.namespace}"
            )
            if not typer.confirm("Are you sure ?"):
                raise typer.Abort()

        bl_chart_folder = ioc_path.parent.parent / BEAMLINE_CHART_FOLDER
        # temporary copy of the beamline chart for destructive modification
        shutil.copytree(bl_chart_folder, self.tmp / BEAMLINE_CHART_FOLDER)

        config_folder = ioc_path / CONFIG_FOLDER
        self._do_deploy(config_folder)

    def deploy(self):
        """
        Generate an IOC helm chart and deploy it to the cluster
        """
        if not self.version:
            raise typer.Exit("ERROR: version is required")

        run_command(
            f"git clone {self.beamline_repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={self.version}",
            interactive=False,
        )
        if not self.ioc_config_folder.exists():
            log.error(
                f"{self.ioc_name} does not exist in {self.beamline_repo} version {self.version}"
            )
            raise typer.Exit(1)

        self._do_deploy(self.ioc_config_folder)

    def _do_deploy(self, config_folder: Path):
        """
        Generate an on the fly chart using beamline chart with config folder.
        Deploy the resulting helm chart to the cluster.
        """
        # values.yaml is a peer to the config folder
        values_path = config_folder.parent / "values.yaml"

        # add the config folder to the helm chart
        self.bl_config_folder.symlink_to(config_folder)

        # get library charts
        run_command(f"helm dependency update {self.bl_chart_folder}", interactive=False)
        # use helm to install the chart
        self._install(
            values=values_path,
        )

    def _install(
        self,
        values: Path,
    ):
        """
        Execute helm install command
        """

        helm_cmd = "template" if self.template else "upgrade --install"
        # complicated stderr filter to suppress helm symlink warnings
        cmd = (
            f"bash -c "
            f'"helm {helm_cmd} {self.ioc_name} {self.bl_chart_folder} '
            f"--version {self.version} --namespace {self.namespace} -f {values} "
            f"--set ioc_name={self.ioc_name} --set ioc_version={self.version} "
            f" 2> >(grep -v 'found symbolic link' >&2)\""
        )
        if self.args:
            cmd += f" {self.args}"

        output = run_command(cmd, interactive=False)
        typer.echo(output)
