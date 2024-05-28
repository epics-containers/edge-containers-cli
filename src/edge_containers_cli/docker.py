"""
Utility functions for working interacting with docker / podman CLI
"""

import re
from pathlib import Path
from time import sleep
from typing import Optional

import typer

import edge_containers_cli.globals as globals
import edge_containers_cli.shell as shell
from edge_containers_cli.logging import log


class Docker:
    """
    A class for interacting with the docker / podman CLI. Abstracts away
    which CLI is being used and whether buildx is available.
    """

    def __init__(self, devcontainer: bool = False, check: bool = True):
        self.devcontainer = devcontainer
        self.docker: str = "podman"
        self.is_docker: bool = False
        self.is_buildx: bool = False
        if check:
            self._check_docker()

    def _check_docker(self):
        """
        Decide if we will use docker or podman cli.

        Also look to see if buildx is available.

        Prefer docker if it is installed, otherwise use podman

        Returns:
            Tuple[str, bool]: docker command, is_docker, is_buildx
        """
        if globals.EC_CONTAINER_CLI:
            self.docker = globals.EC_CONTAINER_CLI
        else:
            # default to podman if we do not find a docker>=20.0.0
            result = shell.run_command(
                "docker --version", interactive=False, error_OK=True
            )
            match = re.match(r"[^\d]*(\d+)", str(result))
            if match is not None:
                version = int(match.group(1))
                if version >= 20:
                    self.docker, self.is_docker = "docker", True
                    log.debug(f"using docker {result}")

        result = shell.run_command(
            f"{self.docker} buildx version", interactive=False, error_OK=True
        )
        self.is_buildx = "docker/buildx" in str(result)

        log.debug(f"buildx={self.is_buildx} ({result})")

    def exec(
        self,
        container: str,
        command: str,
        args: str = "",
        interactive: bool = True,
        errorOK: bool = False,
    ):
        """
        execute a command in a local IOC instance
        """
        self.is_running(container, error=True)
        args = f"{args} " if args else ""
        result = shell.run_command(
            f'{self.docker} exec {args}{container} bash -c "{command}"',
            interactive=interactive,
            error_OK=errorOK,
        )
        return result

    def remove(self, container: str):
        """
        Stop and delete a container. Don't fail if it does not exist
        """
        self.stop(container)
        shell.run_command(
            f"{self.docker} rm -f {container}", error_OK=True, interactive=False
        )

    def stop(self, container: str):
        """
        Stop a container
        """
        shell.run_command(
            f"{self.docker} stop -t0 {container}", error_OK=True, interactive=False
        )

    def attach(self, container: str):
        """
        attach to a container
        """
        self.is_running(container, error=True)
        # quitting the attach returns an error code so we have to ignore it
        shell.run_command(f"{self.docker} attach {container}", error_OK=True)

    def logs(
        self,
        container: str,
        previous: bool = False,
        follow: bool = False,
        stdout: bool = False,
    ) -> Optional[str | bool]:
        """
        show logs from a container
        """
        self.is_running(container, error=True)
        prev = " -p" if previous else ""
        fol = " -f" if follow else ""

        if stdout:
            a = shell.run_command(
                f"{self.docker} logs{prev}{fol} {container}",
                interactive=False,
                show=False,
                error_OK=True,
            )
            return a
        else:
            shell.run_command(f"{self.docker} logs{prev}{fol} {container}")

    def is_running(self, container: str, retry=1, error=False):
        """
        verify that a given container is up and running
        """
        for _i in range(retry):
            result = shell.run_command(
                f"{self.docker} ps -f name={container} --format '{{{{.Names}}}}'",
                interactive=False,
            )
            if container in str(result):
                return True
            sleep(0.5)
        else:
            if error:
                log.error(f"{container} is not running")
                raise typer.Exit(1)
            return False

    def run_tool(
        self, image: str, args: str = "", entrypoint: str = "", interactive=False
    ):
        """
        run a command in a container - mount the current directory
        so that the command can see files passed on the CLI
        """
        if entrypoint:
            entrypoint = f" --entrypoint {entrypoint}"
        cwd = Path.cwd().resolve()
        mount = f"-w {cwd} -v {cwd}:{cwd} -v /tmp:/tmp"
        shell.run_command(
            f"{self.docker} run{entrypoint} --rm {mount} {image} {args}",
            interactive=True,
        )
