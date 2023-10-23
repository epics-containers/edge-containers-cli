"""
Utility functions for working interacting with docker / podman CLI
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple

from epics_containers_cli.logging import log
from epics_containers_cli.shell import EC_CONTAINER_CLI, run_command

IMAGE_TAG = "local"
MOUNTED_FILES = ["/.bashrc", "/.inputrc", "/.bash_eternal_history"]

# podman needs this security option to allow containers to mount tmp etc.
PODMAN_OPT = " --security-opt=label=type:container_runtime_t"


class Docker:
    """
    A class for interacting with the docker / podman CLI. Abstracts away
    which CLI is being used and whether buildx is available.
    """

    def __init__(self, devcontainer: bool = False):
        self.devcontainer = devcontainer
        self.docker, self.is_docker, self.is_buildx = self._check_docker()

    def _check_docker(self) -> Tuple[str, bool, bool]:
        """
        Decide if we will use docker or podman cli.

        Also look to see if buildx is available.

        Prefer docker if it is installed, otherwise use podman

        Returns:
            Tuple[str, bool]: docker command, is_docker, is_buildx
        """
        # defaults
        docker_cmd, is_docker = "podman", False

        if EC_CONTAINER_CLI:
            docker_cmd = EC_CONTAINER_CLI
        else:
            # default to podman if we do not find a docker>=20.0.0
            result = run_command("docker --version", interactive=False, error_OK=True)
            match = re.match(r"[^\d]*(\d+)", result)
            if match is not None:
                version = int(match.group(1))
                if version >= 20:
                    docker_cmd, is_docker = "docker", True
                    log.debug(f"using docker {result}")

        result = run_command(
            f"{docker_cmd} buildx version", interactive=False, error_OK=True
        )
        is_buildx = result and "buildah" not in result

        log.debug(f"buildx={is_buildx} ({result})")

        return docker_cmd, is_docker, is_buildx

    def _all_params(self, args: str, mounts: List[Path], exec: bool = False):
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
            for file in MOUNTED_FILES + mounts:
                file_path = Path(file)
                if file_path.exists():
                    volumes += f" -v {file}:/root/{file_path.name}"
            for mount in mounts:
                volumes += f" -v {mount}"

            log.debug(f"env={env} volumes={volumes} opts={opts}")

            params = f"{env}{opts}{volumes}" + f" {args}" if args else ""
        else:
            params = f"{opts}" + (f"{args}" if args else "")

        return params

    def run(self, name: str, mounts: List[Path], args: str = ""):
        """
        run a command in a local container
        """
        params = self._all_params(args, mounts=mounts)
        run_command(f"{self.docker} run --rm --name {name} {params}", interactive=True)

    def build(self, container: str, args: str = ""):
        """
        build a container
        """
        params = self._all_params(args)
        run_command(f"{self.docker} build {params} {container}")

    def exec(self, command: str, container: str, args: str = ""):
        """
        execute a command in a local IOC instance
        """
        config = self._all_params(args, exec=True)
        run_command(f'{self.docker} exec {config} {container} bash -c "{command}"')

    def remove(self, container: str):
        """
        Stop and delete a container. Don't fail if it does not exist
        """
        run_command(
            f"{self.docker} stop -t0 {container}", error_OK=True, interactive=False
        )
        run_command(f"{self.docker} rm {container}", error_OK=True, interactive=False)
