"""
Utility functions for working interacting with docker / podman CLI
"""
import re
import sys
from pathlib import Path
from time import sleep
from typing import List, Optional

import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.globals import Architecture
from epics_containers_cli.logging import log
from epics_containers_cli.shell import run_command

IMAGE_TAG = "local"
MOUNTED_FILES = ["/.bashrc", "/.inputrc", "/.bash_eternal_history"]

# podman needs this security option to allow containers to mount tmp etc.
PODMAN_OPT = " --security-opt=label=type:container_runtime_t"


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
        if glob_vars.EC_CONTAINER_CLI:
            self.docker = glob_vars.EC_CONTAINER_CLI
        else:
            # default to podman if we do not find a docker>=20.0.0
            result = run_command("docker --version", interactive=False, error_OK=True)
            match = re.match(r"[^\d]*(\d+)", str(result))
            if match is not None:
                version = int(match.group(1))
                if version >= 20:
                    self.docker, self.is_docker = "docker", True
                    log.debug(f"using docker {result}")

        result = run_command(
            f"{self.docker} buildx version", interactive=False, error_OK=True
        )
        self.is_buildx = "docker/buildx" in result

        log.debug(f"buildx={self.is_buildx} ({result})")

    def _all_params(
        self, args: str, mounts: Optional[List[Path]] = None, exec: bool = False
    ):
        """
        set up parameters for call to docker/podman
        """
        opts = PODMAN_OPT if not self.is_docker and not exec else ""

        if self.devcontainer:
            if sys.stdin.isatty():
                # interactive
                env = "-e DISPLAY -e SHELL -e TERM -it"
            else:
                env = "-e DISPLAY -e SHELL"

            volumes = ""
            for file in MOUNTED_FILES:
                file_path = Path(file)
                if file_path.exists():
                    volumes += f" -v {file}:/root/{file_path.name}"
            if mounts is not None:
                for mount in mounts:
                    volumes += f" -v {mount}"

            log.debug(f"env={env} volumes={volumes} opts={opts}")

            params = f"{env}{opts}{volumes}" + f" {args}" if args else ""
        else:
            params = f"{opts}" + (f"{args}" if args else "")

        return params

    def run(self, name: str, args: str = "", mounts: Optional[List[Path]] = None):
        """
        run a command in a local container
        """
        params = self._all_params(args, mounts=mounts)
        run_command(f"{self.docker} run --rm --name {name} {params}", interactive=True)

    def build(
        self,
        context: str,
        name: str,
        target: str,
        args: str = "",
        cache_from: str = "",
        cache_to: str = "",
        push: bool = False,
        arch: Architecture = Architecture.linux,
    ):
        """
        build a container
        """
        if self.is_buildx:
            cmd = f"{self.docker} buildx"
            run_command(
                f"{cmd} create --driver docker-container --use", interactive=False
            )
            args += f" --cache-from={cache_from}" if cache_from else ""
            args += f" --cache-to={cache_to},mode=max" if cache_to else ""
            args += " --push" if push else " --load "
        else:
            cmd = f"{self.docker}"

        t_arch = f" --build-arg TARGET_ARCHITECTURE={arch}" if self.devcontainer else ""

        run_command(f"{cmd} build --target {target}{t_arch} {args} -t {name} {context}")

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
        result = run_command(
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
        run_command(
            f"{self.docker} rm -f {container}", error_OK=True, interactive=False
        )

    def stop(self, container: str):
        """
        Stop a container
        """
        run_command(
            f"{self.docker} stop -t0 {container}", error_OK=True, interactive=False
        )

    def attach(self, container: str):
        """
        attach to a container
        """
        self.is_running(container, error=True)
        # quitting the attach returns an error code so we have to ignore it
        run_command(f"{self.docker} attach {container}", error_OK=True)

    def logs(self, container: str, previous: bool = False, follow: bool = False):
        """
        show logs from a container
        """
        self.is_running(container, error=True)
        prev = " -p" if previous else ""
        fol = " -f" if follow else ""

        run_command(f"{self.docker} logs{prev}{fol} {container}")

    def is_running(self, container: str, retry=1, error=False):
        """
        verify that a given container is up and running
        """
        for i in range(retry):
            result = run_command(
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
        run_command(
            f"{self.docker} run{entrypoint} --rm {mount} {image} {args}",
            interactive=True,
        )
