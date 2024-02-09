import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

import ec_cli.globals as globals
import ec_cli.shell as shell
from ec_cli.utils import chdir, check_ioc_instance_path, cleanup_temp, log


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
        branch: Optional[str] = None,
    ):
        """
        Create a helm chart from a local or a remote repo
        """
        self.service_name = service_name
        self.beamline_repo = repo
        self.namespace = namespace
        self.args = args
        self.version = version or datetime.strftime(
            datetime.now(), "%Y.%-m.%-d-b%-H.%-M"
        )
        self.template = template
        self.branch = branch

        self.tmp = Path(tempfile.mkdtemp())

    def __del__(self):
        if hasattr(self, "tmp"):
            cleanup_temp(self.tmp)

    def deploy_local(self, service_path: Path, yes: bool = False):
        """
        Deploy a local IOC helm chart directly to the cluster with dated beta version
        """

        ioc_name, service_path = check_ioc_instance_path(service_path)

        if not yes and not self.template:
            typer.echo(
                f"Deploy {ioc_name} TEMPORARY version {self.version} "
                f"from {service_path} to domain {self.namespace}"
            )
            if not typer.confirm("Are you sure ?"):
                raise typer.Abort()

        bl_chart_folder = service_path.parent.parent / globals.BEAMLINE_CHART_FOLDER
        # temporary copy of the beamline chart for destructive modification
        shutil.copytree(bl_chart_folder, self.tmp / globals.BEAMLINE_CHART_FOLDER)

        self._do_deploy()

    def deploy(self):
        """
        Generate an IOC helm chart and deploy it to the cluster
        """
        if not self.version:
            log.error("Version not found")
            raise typer.Exit(1)

        shell.run_command(
            f"git clone {self.beamline_repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={self.branch}",
            interactive=False,
        )

        self._do_deploy(self.tmp / "services" / self.service_name)

    def _do_deploy(self, service_folder: Path):
        """
        Generate an on the fly chart using beamline chart with config folder.
        Deploy the resulting helm chart to the cluster.
        """

        chart_paths = list(service_folder.glob(f"{globals.SHARED_CHARTS_FOLDER}/*"))
        chart_paths.append(service_folder)

        # package up the charts to get the appVersion set
        for chart in chart_paths:
            shell.run_command(f"helm dependency update {chart}", interactive=False)

        with chdir(service_folder):
            shell.run_command(
                f"helm package {service_folder} --app-version {self.version}",
                interactive=False,
            )
            # find the packaged chart
            chart_file = list(service_folder.glob("*.tgz"))[0]

        # use helm to install the chart
        self._install(chart_file)

    def _install(self, helm_chart_folder: Path):
        """
        Execute helm install command
        """

        helm_cmd = "template" if self.template else "upgrade --install"
        # complicated stderr filter to suppress helm symlink warnings
        cmd = (
            f"bash -c "
            f'"'
            f"helm {helm_cmd} {self.service_name} {helm_chart_folder} "
            f"--version {self.version} --namespace {self.namespace} "
            f"{self.args}"
            f" 2> >(grep -v 'found symbolic link' >&2) "
            f'"'
        )

        output = shell.run_command(cmd, interactive=False)
        typer.echo(output)
