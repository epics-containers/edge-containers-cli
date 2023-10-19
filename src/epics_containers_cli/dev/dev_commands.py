import re
import sys
import time
from pathlib import Path
from typing import Optional

import typer

from epics_containers_cli.git import get_git_name, get_image_name
from epics_containers_cli.logging import log
from epics_containers_cli.shell import EC_CONTAINER_CLI, run_command
from epics_containers_cli.utils import check_ioc_instance_path, get_instance_image_name

from ..globals import (
    CONFIG_FOLDER,
    IOC_CONFIG_FOLDER,
    IOC_START,
    Architecture,
    Targets,
)

dev = typer.Typer()

IMAGE_TAG = "local"
MOUNTED_FILES = ["/.bashrc", "/.inputrc", "/.bash_eternal_history"]


# parameters for container launches
PODMAN_OPT = " --security-opt=label=type:container_runtime_t"
# NOTE: I have removed --net host so that tested IOCs are isolated
# TODO: review this choice when implementing GUIs


class DevCommands:
    """
    A class to implement the set of commands in the 'dev' namespace
    """

    def __init__(self):
        self.docker = "podman"
        self.is_docker = False
        self.is_buildx = False
        self._check_docker()

    def _check_docker(self):
        """
        Decide if we will use docker or podman cli.

        Also look to see if buildx is available.

        Prefer docker if it is installed, otherwise use podman
        """
        if EC_CONTAINER_CLI:
            self.docker = EC_CONTAINER_CLI
        else:
            # default to podman if we do not find a docker>=20.0.0
            result = run_command("docker --version", interactive=False, error_OK=True)
            match = re.match(r"[^\d]*(\d+)", result)
            if match is not None:
                version = int(match.group(1))
                if version >= 20:
                    self.docker, self.is_docker = "docker", True
                    log.debug(f"using docker {result}")

        result = run_command(
            f"{self.docker} buildx version", interactive=False, error_OK=True
        )
        if result and "buildah" not in result:
            self.is_buildx = True

        log.debug(f"buildx={self.is_buildx} ({result})")

    def _all_params(self, exec: bool = False):
        """
        set up parameters for call to docker/podman
        """

        # TODO - can we tidy up the argument generation ?
        # we are trying to cope with building / running / execing / stopping
        # containers with podman / docker / buildx and at present the
        # code looks a little opaque I figure a nice dictionary definition
        # of the matrix of options might work better

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

        opts = PODMAN_OPT if not self.is_docker and not exec else ""

        log.debug(f"env={env} volumes={volumes} opts={opts}")

        return f"{env}{volumes}{opts}"

    def _do_launch(
        self,
        ioc_name: str,
        target: Targets,
        image: str,
        execute: str,
        args: str,
        mounts: list,
    ):
        """
        Common code for launch and launch_local CLI commands
        """
        log.info(
            f"launching {ioc_name} image:{image} target:{target} "
            f"execute:{execute} args:{args} mounts:{mounts}"
        )

        # make sure there is not already an IOC of this name running
        run_command(
            f"{self.docker} stop -t0 {ioc_name}", error_OK=True, interactive=False
        )
        run_command(f"{self.docker} rm {ioc_name}", error_OK=True, interactive=False)

        start_script = f"-c '{execute}'"

        args = " " + args.strip("' ") if args else ""
        config = self._all_params() + f' {" ".join(mounts)}' + args

        if target == Targets.developer:
            image = image.replace(Targets.runtime, Targets.developer)

        run_command(
            f"{self.docker} run --rm --entrypoint 'bash' --name {ioc_name} {config}"
            f" {image} {start_script}",
            interactive=True,
        )

    def launch_local(
        self,
        ioc_instance: Optional[Path],
        generic_ioc: Path,
        execute: Optional[str],
        target: Targets,
        tag: str,
        args: str,
        ioc_name: str,
    ):
        """
        Launch a locally built generic IOC container from the image cache
        """
        log.debug(
            f"launch: ioc_instance={ioc_instance} generic_ioc={generic_ioc}"
            f" execute={execute} target={target} args={args}"
        )

        mounts = []
        if ioc_instance is None:
            execute = execute or "bash"
        else:
            ioc_instance = ioc_instance.resolve()
            if (ioc_instance / CONFIG_FOLDER).exists():
                ioc_instance = ioc_instance / CONFIG_FOLDER
            mounts.append(f"-v {ioc_instance}:{IOC_CONFIG_FOLDER}")
            log.debug(f"mounts: {mounts}")
            execute = f"{IOC_START}; bash"

        repo, _ = get_git_name(generic_ioc)
        image = get_image_name(repo, target=target) + f":{tag}"

        self._do_launch(ioc_name, target, image, execute, args, mounts)

    def launch(
        self,
        ioc_instance: Path,
        execute: str,
        target: Targets,
        image: str,
        tag: Optional[str],
        args: str,
        ioc_name: str,
    ):
        """
        Launch and IOC instance
        """
        log.debug(
            f"launch: ioc_folder={ioc_instance} image={image}"
            f" execute={execute} target={target} args={args}"
        )

        ioc_name_std, ioc_path = check_ioc_instance_path(ioc_instance)
        ioc_name = ioc_name or ioc_name_std

        mounts = [f"-v {ioc_path}/{CONFIG_FOLDER}:{IOC_CONFIG_FOLDER}"]

        image_name = image or get_instance_image_name(ioc_path, tag)

        self._do_launch(ioc_name, target, image_name, execute, args, mounts)

    def debug_last(self, generic_ioc: Path, mount_repos: bool):
        """
        Launch the most recently partially built container image
        """
        last_image = run_command(
            f"{self.docker} images | awk '{{print $3}}' | awk 'NR==2'",
            interactive=False,
        )

        params = self._all_params()
        _, repo_root = get_git_name(generic_ioc)

        if mount_repos:
            params += f" -v{repo_root}:/epics/ioc/${repo_root.name}"

        run_command(
            f"{self.docker} run --entrypoint bash --rm --name debug_build "
            f"{params} {last_image}"
        )

    def versions(self, generic_ioc: Path, arch: Architecture, image: str):
        """
        get the versions of a container image available in the registry
        """
        if image == "":
            repo, _ = get_git_name(generic_ioc)
            image = image or get_image_name(repo, arch)

        log.info(f"looking for versions of image {image}")
        run_command(
            f"{self.docker} run --rm quay.io/skopeo/stable "
            f"list-tags docker://{image}"
        )

    def stop(self, ioc_name: str):
        """
        Stop a locally running container
        """
        run_command(f"{self.docker} stop -t0 {ioc_name}", interactive=False)

    def exec(self, command: str, ioc_name: str):
        """
        execute a command in a locally running container
        """
        config = self._all_params(exec=True)
        run_command(f'{self.docker} exec {config} {ioc_name} bash -c "{command}"')

    def wait_pv(self, pv_name: str, ioc_name: str, attempts: int):
        """
        wait for a local IOC instance to start by monitoring for a PV
        """
        for i in range(attempts):
            result = run_command(
                f'{self.docker} exec {ioc_name} bash -c "caget {pv_name}"',
                interactive=False,
                error_OK=True,
            )
            if str(result).startswith(pv_name):
                break
            time.sleep(1)
        else:
            log.error(f"PV {pv_name} not found in {ioc_name}")
            raise typer.Exit(1)

    def build(
        self,
        generic_ioc: Path,
        tag: str,
        arch: Architecture,
        platform: str,
        buildx: bool,
        cache: bool,
        cache_to: Optional[str],
        cache_from: Optional[str],
        push: bool,
        rebuild: bool,
    ):
        """
        build a local image from a Dockerfile
        """
        repo, _ = get_git_name(generic_ioc)
        args = f" --platform {platform} {'--no-cache' if not cache else ''}"

        if self.is_buildx and buildx:
            cmd = f"{self.docker} buildx"
            run_command(
                f"{cmd} create --driver docker-container --use", interactive=False
            )
            args += f" --cache-from={cache_from}" if cache_from else ""
            args += f" --cache-to={cache_to},mode=max" if cache_to else ""
            args += " --push" if push else " --load "
        else:
            cmd = f"{self.docker}"

        for target in Targets:
            image = get_image_name(repo, arch, target)
            image_name = f"{image}:{tag}"

            if not rebuild:
                result = run_command(
                    "{self.docker} images -q {image_name}", interactive=False
                )
                if result:
                    log.info(f"skipping build of {image} as it already exists")
                    continue

            run_command(
                f"{cmd} build --target {target} --build-arg TARGET_ARCHITECTURE={arch}"
                f"{args} -t {image_name} {generic_ioc}"
            )
