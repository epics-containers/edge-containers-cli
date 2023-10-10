import os
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import jinja2
import typer

from epics_containers_cli.globals import BEAMLINE_CHART_FOLDER, CONFIG_FOLDER
from epics_containers_cli.logging import log
from epics_containers_cli.shell import run_command


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
        self.repo = repo
        self.domain = domain
        self.args = args
        self.version = version or datetime.strftime(
            datetime.now(), "%Y.%-m.%-d-b%-H.%-M"
        )
        self.template = template

        self.tmp = Path(mkdtemp())

        self.bl_chart_folder = self.tmp / BEAMLINE_CHART_FOLDER
        self.jinja_path = self.bl_chart_folder / "Chart.yaml.jinja"
        self.bl_chart_path = self.bl_chart_folder / "Chart.yaml"
        self.bl_config_folder = self.bl_chart_folder / CONFIG_FOLDER

        self.ioc_config_folder = self.tmp / "iocs" / str(self.ioc_name) / CONFIG_FOLDER

    def __del__(self):
        # keep the tmp folder if debug is enabled for inspection
        if log.level != "DEBUG":
            if hasattr(self, "tmp"):
                shutil.rmtree(self.tmp, ignore_errors=True)

    def deploy_local(self, ioc_path: Path, yes: bool = False):
        """
        Deploy a local IOC helm chart directly to the cluster with dated beta version
        """

        ioc_path = ioc_path.absolute()
        ioc_name = ioc_path.name.lower()
        if (
            not (ioc_path / "values.yaml").exists()
            or not (ioc_path / CONFIG_FOLDER).is_dir()
        ):
            log.error("ERROR: IOC instance requires values.yaml and config")
            raise typer.Exit(1)

        if not yes and not self.template:
            typer.echo(
                f"Deploy {ioc_name} TEMPORARY version {self.version} "
                f"from {ioc_path} to domain {self.domain}"
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
            f"git clone {self.repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={self.version}",
            interactive=False,
        )
        self._do_deploy(self.ioc_config_folder)

    def _do_deploy(self, config_folder: Path):
        """
        Generate an on the fly chart using beamline chart with config folder
        and generated Chart.yaml. Deploy the resulting helm chart to the cluster.
        """
        # values.yaml is a peer to the config folder
        values_path = config_folder.parent / "values.yaml"

        # render a Chart.yaml from the jinja template
        template = jinja2.Template(self.jinja_path.read_text())
        chart = template.render(ioc_name=self.ioc_name, ioc_version=self.version)
        self.bl_chart_path.write_text(chart)

        # add the config folder to the helm chart
        self.bl_config_folder.symlink_to(config_folder)

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
            f"--version {self.version} --namespace {self.domain} -f {values}"
            f" 2> >(grep -v 'found symbolic link' >&2)\""
        )
        if self.args:
            cmd += f" {self.args}"

        output = run_command(cmd, interactive=False)
        typer.echo(output)

    def versions(self):
        typer.echo(f"Available instance versions for {self.ioc_name}:")

        run_command(f"git clone {self.repo} {self.tmp}", interactive=False)

        ioc_name = Path(self.ioc_name).name
        cmd = "git tag"
        os.chdir(self.tmp)
        result = run_command(cmd, interactive=False)
        log.debug(f"checking these tags for changes in the instance: {result}")

        tags = result.split("\n")
        for tag in tags:
            if tag == "":
                continue
            cmd = f"git diff --name-only {tag} {tag}^"
            result = run_command(cmd, interactive=False)

            if ioc_name in result:
                typer.echo(f"  {tag}")