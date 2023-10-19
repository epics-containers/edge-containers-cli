"""
Implements functions for deploying and managing local ioc instances using
local docker standalone. This is an initial experimetal implementation.
In future we could support remote deployment and possibly creating
portainer mainfests.

However, for the moment, Using this by connecting to each server and running
'ec deploy <ioc_name> <ioc_version> and then managing the network with a
tool like Portainer is a decent workflow.
"""

from pathlib import Path
from typing import Optional

import typer

from epics_containers_cli.globals import Context
from epics_containers_cli.shell import run_command


class IocLocalCommands:
    """
    A class for implementing the ioc command namespace
    """

    def __init__(self, ctx: Optional[Context], ioc_name: str = ""):
        self.beamline_repo: str = ""
        if ctx is not None:
            self.beamline_repo = ctx.beamline_repo
        self.ioc_name: str = ioc_name

    def attach(self):
        run_command(f"docker attach -it {self.ioc_name}")

    def delete(self):
        if not typer.confirm(
            f"This will remove all versions of {self.ioc_name} "
            "from the cluster. Are you sure ?"
        ):
            raise typer.Abort()

        run_command(f"docker stop -t0 {self.ioc_name}")
        run_command(f"docker rm -f {self.ioc_name}")

    def deploy_local(self, ioc_instance: Path, yes: bool, args: str):
        pass

    def deploy(self, ioc_name: str, version: str, args: str):
        pass

    def exec(self):
        run_command(f"docker exec -it {self.ioc_name} bash")

    def logs(self, prev: bool, follow: bool):
        previous = "-p" if prev else ""
        fol = "-f" if follow else ""

        run_command(f"docker logs {previous} {fol} {self.ioc_name}")

    def restart(self):
        run_command(f"docker restart {self.ioc_name}")

    def start(self):
        run_command(f"docker start {self.ioc_name}")

    def stop(self):
        run_command(f"docker stop {self.ioc_name}")
