"""
Implements functions for deploying and managing local ioc instances using
local docker standalone. This is an initial experimental implementation.
In future we could support remote deployment and possibly creating
portainer manifests.

However, for the moment, Using this by connecting to each server and running
'ec deploy <ioc_name> <ioc_version> and then managing the network with a
tool like Portainer is a decent workflow.
"""

import shutil
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.docker import Docker
from epics_containers_cli.globals import CONFIG_FOLDER, IOC_CONFIG_FOLDER, Context
from epics_containers_cli.logging import log
from epics_containers_cli.shell import check_beamline_repo, run_command
from epics_containers_cli.utils import check_ioc_instance_path, get_instance_image_name

PS_FORMAT = "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.ID}}"


class IocLocalCommands:
    """
    A class for implementing the ioc command namespace
    """

    def __init__(self, ctx: Optional[Context], ioc_name: str = ""):
        self.beamline_repo: str = ""
        if ctx is not None:
            self.beamline_repo = ctx.beamline_repo

        self.ioc_name: str = ioc_name

        self.tmp = Path(mkdtemp())
        self.ioc_folder = self.tmp / "iocs" / ioc_name
        self.docker = Docker()

    def __del__(self):
        # keep the tmp folder if debug is enabled for inspection_del
        if not glob_vars.EC_DEBUG:
            if hasattr(self, "tmp"):
                shutil.rmtree(self.tmp, ignore_errors=True)

    def attach(self):
        self.docker.attach(self.ioc_name)

    def delete(self):
        if not typer.confirm(
            f"This will remove the IOC container {self.ioc_name} "
            "from the this server. Are you sure ?"
        ):
            raise typer.Abort()
        self.docker.remove(self.ioc_name)

    def _do_deploy(self, ioc_instance: Path, version: str, args: str):
        ioc_name, ioc_path = check_ioc_instance_path(ioc_instance)

        image = get_instance_image_name(ioc_instance)
        log.debug(f"deploying {ioc_instance} with image {image}")
        config = ioc_instance / CONFIG_FOLDER
        ioc_name = ioc_instance.name
        volume = f"{ioc_name}_config"

        self.docker.remove(ioc_name)
        run_command(f"{self.docker.docker} volume rm -f {volume}", interactive=False)
        run_command(f"{self.docker.docker} volume create {volume}", interactive=False)

        vol = f"-v {volume}:{IOC_CONFIG_FOLDER}"
        label = f"-l is_IOC=true -l version={version}"
        cmd = f"run -dit --net host --restart unless-stopped {label} {vol} {args}"
        dest = f"{ioc_name}:{IOC_CONFIG_FOLDER}"

        run_command(f"{self.docker.docker} {cmd} --name {ioc_name} {image}")
        run_command(f"{self.docker.docker} cp {config} {dest}", interactive=False)

    def deploy_local(self, ioc_instance: Path, yes: bool, args: str):
        """
        Use a local copy of an ioc instance definition to deploy a temporary
        version of the IOC to the local docker instance
        """
        version = datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")
        if not yes:
            typer.echo(
                f"Deploy TEMPORARY version {version} "
                f"from {ioc_instance} to the local docker instance"
            )
            if not typer.confirm("Are you sure ?"):
                raise typer.Abort()
        self._do_deploy(ioc_instance, version, args)

    def deploy(self, ioc_name: str, version: str, args: str):
        """
        deploy a tagged version of an ioc from a remote repo
        """

        check_beamline_repo(self.beamline_repo)

        run_command(
            f"git clone {self.beamline_repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={version}",
            interactive=False,
        )

        self._do_deploy(self.ioc_folder, version, args)

    def exec(self):
        self.docker.exec(self.ioc_name, "bash", args="-it")

    def logs(self, prev: bool, follow: bool):
        self.docker.logs(self.ioc_name, prev, follow)

    def restart(self):
        run_command(f"{self.docker.docker} restart {self.ioc_name}")

    def start(self):
        run_command(f"{self.docker.docker} start {self.ioc_name}")

    def stop(self):
        run_command(f"{self.docker.docker} stop {self.ioc_name}")

    def ps(self, all: bool, wide: bool):
        all = " --all" if all else ""
        run_command(
            f"{self.docker.docker} ps{all} --filter label=is_IOC=true "
            f'--format "{PS_FORMAT}"'
        )
