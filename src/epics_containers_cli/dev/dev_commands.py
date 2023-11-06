import time
from pathlib import Path
from typing import Optional

import typer

from epics_containers_cli.docker import Docker
from epics_containers_cli.git import get_git_name, get_image_name
from epics_containers_cli.logging import log
from epics_containers_cli.shell import run_command
from epics_containers_cli.utils import check_ioc_instance_path, get_instance_image_name

from ..globals import (
    CONFIG_FOLDER,
    IOC_CONFIG_FOLDER,
    IOC_START,
    Architecture,
    Targets,
)

dev = typer.Typer()


class DevCommands:
    """
    A class to implement the set of commands in the 'dev' namespace
    """

    def __init__(self):
        self.docker = Docker(devcontainer=True)

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
        self.docker.remove(ioc_name)

        start_script = f"-c '{execute}'"

        if target == Targets.developer:
            image = image.replace(Targets.runtime, Targets.developer)

        args = " " + args.strip("'") if args else ""
        self.docker.run(
            name=ioc_name,
            args=f"--entrypoint 'bash'{args} {image} {start_script}",
            mounts=mounts,
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
            mounts.append(f"{ioc_instance}:{IOC_CONFIG_FOLDER}")
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

        mounts = [f"{ioc_path}/{CONFIG_FOLDER}:{IOC_CONFIG_FOLDER}"]

        image_name = image or get_instance_image_name(ioc_path, tag)

        self._do_launch(ioc_name, target, image_name, execute, args, mounts)

    def debug_last(self, generic_ioc: Path, mount_repos: bool):
        """
        Launch the most recently partially built container image
        """
        last_image = run_command(
            self.docker.docker + " images | awk '{print $3}' | awk 'NR==2'",
            interactive=False,
        )

        _, repo_root = get_git_name(generic_ioc)

        if mount_repos:
            mounts = [f"{repo_root}:/epics/ioc/${repo_root.name}"]

        self.docker.run(
            name="debug_build", mounts=mounts, args=f"--entrypoint bash {last_image}"
        )

    def versions(self, generic_ioc: Path, arch: Architecture, image: str):
        """
        get the versions of a container image available in the registry
        """
        if image == "":
            repo, _ = get_git_name(generic_ioc)
            image = image or get_image_name(repo, arch)

        log.info(f"looking for versions of image {image}")
        self.docker.run("versions", f"quay.io/skopeo/stable list-tags docker://{image}")

    def stop(self, ioc_name: str):
        """
        Stop a locally running container
        """
        self.docker.stop(ioc_name)

    def exec(self, ioc_name: str, command: str, args: str = ""):
        """
        execute a command in a locally running container
        """
        self.docker.exec(container=ioc_name, command=command, args=args)

    def wait_pv(self, pv_name: str, ioc_name: str, attempts: int):
        """
        wait for a local IOC instance to start by monitoring for a PV
        """
        for i in range(attempts):
            cmd = f"caget {pv_name}"
            result = self.docker.exec(
                container=ioc_name, command=cmd, interactive=False, errorOK=True
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
        cache: bool,
        cache_from: Optional[str],
        cache_to: Optional[str],
        push: bool,
        rebuild: bool,
        target: Optional[str],
        suffix: Optional[str],
    ):
        """
        build a local image from a Dockerfile
        """
        repo, _ = get_git_name(generic_ioc)
        args = f"--platform {platform} {'--no-cache' if not cache else ''}"

        if target is None:
            targets = [Targets.developer.value, Targets.runtime.value]
        else:
            targets = [target]
        for target in targets:
            image = get_image_name(repo, arch, target, suffix)
            image_name = f"{image}:{tag}"

            if not rebuild:
                result = run_command(
                    "{self.docker.docker} images -q {image_name}", interactive=False
                )
                if result:
                    log.info(f"skipping build of {image} as it already exists")
                    continue

            self.docker.build(
                generic_ioc,
                image_name,
                target,
                args,
                cache_from,
                cache_to,
                push,
                arch,
            )
