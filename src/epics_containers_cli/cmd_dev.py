import os
import re
import sys
from pathlib import Path
from typing import Optional

import typer

from .globals import CONFIG_FOLDER, IOC_CONFIG_FOLDER, IOC_START, Architecture, Targets
from .logging import log
from .shell import EC_CONTAINER_CLI, get_git_name, get_image_name, run_command

dev = typer.Typer()

IMAGE_TAG = "local"
MOUNTED_FILES = ["/.bashrc", "/.inputrc", "/.bash_eternal_history"]


# parameters for container launches
OPTS = "--security-opt=label=type:container_runtime_t --net=host"


def _check_docker():
    """
    Decide if we will use docker or podman cli.

    Prefer docker if it is installed, otherwise use podman
    """
    # environment variable overrides
    if EC_CONTAINER_CLI:
        return EC_CONTAINER_CLI

    # default to podman if we do not find a docker>=20.0.0
    docker = "podman"

    result = run_command("docker --version", interactive=False, error_OK=True)

    version = int(re.match(r"[^\d]*(\d*)", result).group(1))
    log.debug(f"docker version = {version} extracted from  {result}")
    if version >= 20:
        docker = "docker"

    return docker


# the container management CLI to use
DOCKER = _check_docker()


def _all_params():
    if os.isatty(sys.stdin.fileno()):
        # interactive
        env = "-e DISPLAY -e SHELL -e TERM -it"
    else:
        env = "-e DISPLAY -e SHELL"

    volumes = ""
    for file in MOUNTED_FILES:
        file_path = Path(file)
        if file_path.exists():
            volumes += f" -v {file}:/root/{file_path.name}"

    return f"{env} {volumes} {OPTS}"


def _go(
    ioc_name: str, target: Targets, image: str, execute: str, args: str, mounts: list
):
    """
    Common code for launch and launch_local CLI commands
    """
    # make sure there is not already an IOC of this name running
    run_command(f"{DOCKER} rm -f {ioc_name}", error_OK=True)

    start_script = f"-c '{execute}'"

    config = _all_params() + f' {" ".join(mounts)} ' + args

    if target == Targets.developer:
        image = image.replace(Targets.runtime, Targets.developer)

    run_command(
        f"{DOCKER} run --rm --entrypoint 'bash' --name {ioc_name} {config}"
        f" {image} {start_script}",
        interactive=True,
    )


@dev.command()
def launch_local(
    ctx: typer.Context,
    ioc_folder: Optional[Path] = typer.Argument(
        None,
        help="local IOC instance config folder",
        dir_okay=True,
        file_okay=False,
    ),
    ioc: Path = typer.Option(
        ".", help="folder for generic IOC project", dir_okay=True, file_okay=False
    ),
    execute: str = typer.Option(
        f"{IOC_START}; bash",
        help="command to execute in the container. Defaults to executing the IOC",
    ),
    target: Targets = typer.Option(
        Targets.developer, help="choose runtime or developer target"
    ),
    args: str = typer.Option(
        "", help=f"Additional args for {DOCKER}/docker, 'must be quoted'"
    ),
):
    """
    Launch a locally built generic IOC from the local cache with tag "local".
    This can only be run after doing an "ec dev build" in the same generic
    IOC project folder.
    """
    log.debug(
        f"launch: ioc_folder={ioc_folder} ioc={ioc}"
        f" execute={execute} target={target} args={args}"
    )

    mounts = []
    if ioc_folder is not None:
        if (ioc_folder / CONFIG_FOLDER).exists():
            ioc_folder = ioc_folder / CONFIG_FOLDER
            mounts.append(f"-v {ioc_folder}:{IOC_CONFIG_FOLDER}")

    repo, _ = get_git_name(ioc, full=True)
    image = get_image_name(repo, target=target) + ":local"

    _go("generic-ioc", target, image, execute, args, mounts)


@dev.command()
def launch(
    ctx: typer.Context,
    ioc_folder: Path = typer.Argument(
        ...,
        help="local IOC definition folder from domain repo",
        dir_okay=True,
        file_okay=False,
    ),
    execute: str = typer.Option(
        f"{IOC_START}; bash",
        help="command to execute in the container. Defaults to executing the IOC",
    ),
    target: Targets = typer.Option(
        Targets.developer, help="choose runtime or developer target"
    ),
    image: str = typer.Option("", help="override container image to use"),
    args: str = typer.Option(
        "", help=f"Additional args for {DOCKER}/docker, 'must be quoted'"
    ),
):
    """
    Launch an IOC instance using configuration from a domain repo. Or by
    passing a generic IOC image ID. Can be used for local testing of IOC
    instances. You may find the devcontainer a more convenient way to
    do this.
    """
    log.debug(
        f"launch: ioc_folder={ioc_folder} image={image}"
        f" execute={execute} target={target} args={args}"
    )

    mounts = []

    ioc_folder = ioc_folder.resolve()
    ioc_name = ioc_folder.name
    values = ioc_folder / "values.yaml"
    if not values.exists():
        typer.echo(f"values.yaml not found in {ioc_folder}")
        raise typer.Exit(1)
    mounts.append(f"-v {ioc_folder}/{CONFIG_FOLDER}:{IOC_CONFIG_FOLDER}")

    values_text = values.read_text()
    matches = re.findall(r"image: (.*)", values_text)
    if len(matches) == 1:
        image = matches[0]
    else:
        typer.echo(f"image tag definition not found in {values}")
        raise typer.Exit(1)

    _go(ioc_name, target, image, execute, args, mounts)


@dev.command()
def debug_last(
    folder: Path = typer.Argument(Path("."), help="Container project folder"),
    mount_repos: bool = typer.Option(
        True, help="Mount generic IOC repo folder into the container"
    ),
):
    """
    Launches a container with the most recent image build.
    Useful for debugging failed builds - if the last build failed it will
    start the container after the most recent successful build step.
    """
    last_image = run_command(
        f"{DOCKER} images | awk '{{print $3}}' | awk 'NR==2'", interactive=False
    )

    params = _all_params()
    _, repo_root = get_git_name(folder)

    if mount_repos:
        params += f" -v{repo_root}:/epics/ioc/${repo_root.name} "

    run_command(
        f"{DOCKER} run --entrypoint bash --rm --name debug_build "
        f"{params} {last_image}"
    )


@dev.command()
def build(
    ctx: typer.Context,
    folder: Path = typer.Option(Path("."), help="Container project folder"),
    arch: Architecture = typer.Option(
        Architecture.linux, help="choose target architecture"
    ),
    cache: bool = typer.Option(True, help="use --no-cache to do a clean build"),
):
    """
    Build a generic IOC container locally from a container project.

    Builds both developer and runtime targets.
    """
    repo, _ = get_git_name(folder, full=True)

    for target in Targets:
        image = get_image_name(repo, arch, target)
        image_name = f"{image}:{IMAGE_TAG} " f"{'--no-cache' if not cache else ''}"
        run_command(
            f"{DOCKER} build --target {target} --build-arg TARGET_ARCHITECTURE={arch}"
            f" -t {image_name} {folder}"
        )


@dev.command()
def versions(
    ctx: typer.Context,
    folder: Path = typer.Argument(Path("."), help="Generic IOC project folder"),
    arch: Architecture = typer.Option(
        Architecture.linux, help="choose target architecture"
    ),
    image: str = typer.Option("", help="override container image to use"),
):
    """
    List the available versions of the generic IOC container image in the registry

    You can supply the full registry image name e.g.
        ec dev versions --image ghcr.io/epics-containers/ioc-template-linux-developer

    or the local project folder (defaults to .) e.g.
        ec dev versions ../ioc-template
    """
    if image == "":
        repo, _ = get_git_name(folder, full=True)
        image = image or get_image_name(repo, arch)

    typer.echo(f"looking for versions of image {image}")
    run_command(
        f"{DOCKER} run --rm quay.io/skopeo/stable " f"list-tags docker://{image}"
    )


@dev.command()
def stop(
    ctx: typer.Context,
    ioc_folder: Path = typer.Argument(
        ...,
        help="local IOC config folder from domain repo",
        dir_okay=True,
        file_okay=False,
    ),
):
    """
    Stop a running local IOC container
    """
    ioc_name = ioc_folder.name
    run_command(
        f"{DOCKER} stop {ioc_name} -t0",
    )
