"""
Implements functions for deploying and managing local ioc instances using
local docker standalone. This is an initial experimetal implementation.
In future we could support remote deployment and possibly creating
portainer mainfests.

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

from epics_containers_cli.globals import CONFIG_FOLDER, IOC_CONFIG_FOLDER, Context
from epics_containers_cli.logging import log
from epics_containers_cli.shell import check_beamline_repo, run_command
from epics_containers_cli.utils import check_ioc_instance_path, get_instance_image_name


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

    def __del__(self):
        # keep the tmp folder if debug is enabled for inspection
        if log.level != "DEBUG":
            if hasattr(self, "tmp"):
                shutil.rmtree(self.tmp, ignore_errors=True)

    def attach(self):
        run_command(f"docker attach {self.ioc_name}")

    def delete(self):
        if not typer.confirm(
            f"This will remove all versions of {self.ioc_name} "
            "from the cluster. Are you sure ?"
        ):
            raise typer.Abort()

        run_command(f"docker stop -t0 {self.ioc_name}")
        run_command(f"docker rm -f {self.ioc_name}")

    def _do_deploy(self, ioc_instance: Path, version: str, args: str):
        ioc_name, ioc_path = check_ioc_instance_path(ioc_instance)

        image = get_instance_image_name(ioc_instance)
        log.debug(f"deploying {ioc_instance} with image {image}")
        config = ioc_instance / CONFIG_FOLDER
        ioc_name = ioc_instance.name
        volume = f"{ioc_name}_config"

        run_command(f"docker container rm -f {ioc_name}", interactive=False)
        run_command(f"docker volume rm -f {volume}", interactive=False)
        run_command(f"docker volume create {volume}", interactive=False)

        vol = f"-v {volume}:{IOC_CONFIG_FOLDER}"
        label = f"-l is_IOC=true -l version={version}"
        cmd = f"run -dit --net host --restart unless-stopped {label} {vol} {args}"
        dest = f"{ioc_name}:{IOC_CONFIG_FOLDER}"

        run_command(f"docker {cmd} --name {ioc_name} {image}")
        run_command(f"docker cp {config}/* {dest}", interactive=False)

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
        run_command(f"docker exec -it {self.ioc_name} bash")

    def logs(self, prev: bool, follow: bool):
        previous = " -p" if prev else ""
        fol = " -f" if follow else ""

        run_command(f"docker logs{previous}{fol} {self.ioc_name}")

    def restart(self):
        run_command(f"docker restart {self.ioc_name}")

    def start(self):
        run_command(f"docker start {self.ioc_name}")

    def stop(self):
        run_command(f"docker stop {self.ioc_name}")
