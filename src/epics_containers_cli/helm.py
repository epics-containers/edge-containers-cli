import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import jinja2
import typer
from git import GitCommandError, Repo

from epics_containers_cli.globals import BEAMLINE_CHART_FOLDER, CONFIG_FOLDER

from .urls import get_repo_url

RE_TAGS = re.compile(r"[\s\S]*?tag: ([\d.]*).*\n")


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
    ):
        """
        Create a helm chart from a local or a remote repo
        """
        self.ioc_name = ioc_name
        self.repo = get_repo_url(domain)
        self.domain = domain
        self.args = args
        self.version = version or datetime.strftime(
            datetime.now(), "%Y.%-m.%-d-b%-H.%-M"
        )

        tmpdir = TemporaryDirectory()
        self.tmp = Path(tmpdir.name)

        self.bl_chart_folder = self.tmp / BEAMLINE_CHART_FOLDER
        self.jinja_path = self.bl_chart_folder / "Chart.yaml.jinja"
        self.bl_chart_path = self.bl_chart_folder / "Chart.yaml"
        self.bl_config_folder = self.bl_chart_folder / CONFIG_FOLDER

        self.ioc_config_folder = self.tmp / "iocs" / str(self.ioc_name) / CONFIG_FOLDER

    def deploy_local(
        self,
        ioc_path: Path,
        yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
    ):
        """
        Deploy a local IOC helm chart directly to the cluster with dated beta version
        """

        ioc_path = ioc_path.absolute()
        ioc_name = ioc_path.name.lower()
        if (
            not (ioc_path / "values.yaml").exists()
            or not (ioc_path / CONFIG_FOLDER).is_dir()
        ):
            typer.echo("ERROR: IOC instance requires values.yaml and config")
            raise typer.Exit(1)

        if not yes:
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
        """Pull an IOC helm chart and deploy it to the cluster"""
        repo_url = get_repo_url(self.domain)

        if not self.version:
            raise typer.Exit("ERROR: version is required")

        try:
            Repo.clone_from(
                repo_url, self.tmp, depth=1, branch=self.version, single_branch=True
            )

            self._do_deploy(self.ioc_config_folder)
        except GitCommandError as e:
            raise typer.Exit(f"ERROR: no IOC of that version found {e}")

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
        cmd = (
            f"helm upgrade --install {self.ioc_name} {self.bl_chart_folder} "
            f"--version {self.version} --namespace {self.domain} -f {values}"
        )
        if self.args:
            cmd += f" {self.args}"

        result = subprocess.run(cmd, shell=True)

        if result.returncode != 0:
            raise typer.Exit(1)

    def versions(self):
        repo_url = get_repo_url(self.domain)

        try:
            Repo.clone_from(repo_url, to_path=self.tmp)

            cmd = "git tag"
            result = subprocess.run(cmd, cwd=self.tmp, shell=True, capture_output=True)
            # TODO factor out this kind of subprocess handling
            if result.returncode != 0:
                raise typer.Exit(result.stderr.decode())

            tags = result.stdout.decode().split("\n")
            for tag in tags:
                if tag == "":
                    continue
                cmd = f"git diff --name-only {tag} {tag}^"
                result = subprocess.run(
                    cmd, cwd=self.tmp, shell=True, capture_output=True
                )
                if result.returncode != 0:
                    raise typer.Exit(result.stderr.decode())
                if self.ioc_name in result.stdout.decode():
                    typer.echo(f"{tag}")

        except GitCommandError as e:
            raise typer.Exit(f"ERROR: no IOC of that version found {e}")
        except ChildProcessError:
            raise typer.Exit("ERROR: ")
