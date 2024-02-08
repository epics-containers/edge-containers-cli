import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

import ec_cli.globals as globals
import ec_cli.shell as shell
from ec_cli.utils import check_ioc_instance_path, cleanup_temp, log


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

        self.tmp = Path(tempfile.mkdtemp())

        self.ioc_config_folder = (
            self.tmp / "iocs" / str(self.ioc_name) / globals.CONFIG_FOLDER
        )

    def __del__(self):
        if hasattr(self, "tmp"):
            cleanup_temp(self.tmp)

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

        bl_chart_folder = ioc_path.parent.parent / globals.BEAMLINE_CHART_FOLDER
        # temporary copy of the beamline chart for destructive modification
        shutil.copytree(bl_chart_folder, self.tmp / globals.BEAMLINE_CHART_FOLDER)

        config_folder = ioc_path / globals.CONFIG_FOLDER
        self._do_deploy(config_folder)

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
        chart_paths = self.tmp.glob(f"*/{globals.SHARED_CHARTS_FOLDER}/*")
        log.warning(f"chart_paths: {list(chart_paths)}")

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

        # get library charts
        shell.run_command(
            f"helm dependency update {self.bl_chart_folder}", interactive=False
        )
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
            f'"'
            f"helm {helm_cmd} {self.ioc_name} {self.bl_chart_folder} "
            f"--version {self.version} --namespace {self.namespace} -f {values} "
            f"--set ioc_name={self.ioc_name} --set ioc_version={self.version} "
            f"{self.args}"
            f" 2> >(grep -v 'found symbolic link' >&2) "
            f'"'
        )

        output = shell.run_command(cmd, interactive=False)
        typer.echo(output)
