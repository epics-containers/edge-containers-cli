import os
import re
import sys
from pathlib import Path
from typing import Optional

import typer

from .globals import (
    CONFIG_FOLDER,
    IOC_CONFIG_FOLDER,
    IOC_NAME,
    IOC_START,
    Architecture,
    Targets,
)
from .logging import log
from .shell import EC_CONTAINER_CLI, get_git_name, get_image_name, run_command

dev = typer.Typer()

DOCKER_PATH = "docker"
IMAGE_TAG = "local"
MOUNTED_FILES = ["/.bashrc", "/.inputrc", "/.bash_eternal_history"]


# parameters for container launches
OPTS = "--security-opt=label=type:container_runtime_t"
# NOTE: I have removed --net host so that tested IOCs are isolated
# TODO: review this choice when implementing GUIs


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

    result = run_command(f"{DOCKER_PATH} --version", interactive=False, error_OK=True)
    match = re.match(r"[^\d]*(\d+)", result)
    if match is not None:
        version = int(match.group(1))
        log.debug(f"docker version = {version} extracted from  {result}")
        if version >= 20:
            docker = DOCKER_PATH

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
    log.info(
        f"launching {ioc_name} image:{image} target:{target} "
        f"execute:{execute} args:{args} mounts:{mounts}"
    )

    # make sure there is not already an IOC of this name running
    run_command(f"{DOCKER} stop -t0 {ioc_name}", error_OK=True, interactive=False)

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
        exists=True,
    ),
    ioc: Path = typer.Option(
        ".", help="folder for generic IOC project", dir_okay=True, file_okay=False
    ),
    execute: Optional[str] = typer.Option(
        None,
        help="command to execute in the container. Defaults to executing the IOC",
    ),
    target: Targets = typer.Option(
        Targets.developer, help="choose runtime or developer target"
    ),
    tag: str = typer.Option(IMAGE_TAG, help="override image tag to use."),
    args: str = typer.Option(
        "", help=f"Additional args for {DOCKER}/docker, 'must be quoted'"
    ),
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
    ),
):
    """
    Launch a locally built generic IOC from the local cache with tag "local".
    This can only be run after doing an 'ec dev build' in the same generic
    IOC project folder.
    """
    log.debug(
        f"launch: ioc_folder={ioc_folder} ioc={ioc}"
        f" execute={execute} target={target} args={args}"
    )

    mounts = []
    if ioc_folder is None:
        execute = execute or "bash"
    else:
        ioc_folder = ioc_folder.resolve()
        if (ioc_folder / CONFIG_FOLDER).exists():
            ioc_folder = ioc_folder / CONFIG_FOLDER
        mounts.append(f"-v {ioc_folder}:{IOC_CONFIG_FOLDER}")
        log.debug(f"mounts: {mounts}")
        execute = f"{IOC_START}; bash"

    repo, _ = get_git_name(ioc, full=True)
    image = get_image_name(repo, target=target) + f":{tag}"

    _go(ioc_name, target, image, execute, args, mounts)


@dev.command()
def launch(
    ctx: typer.Context,
    ioc_folder: Path = typer.Argument(
        ...,
        help="local IOC definition folder from domain repo",
        dir_okay=True,
        file_okay=False,
        exists=True,
    ),
    execute: str = typer.Option(
        f"{IOC_START}; bash",
        help="command to execute in the container. Defaults to executing the IOC",
    ),
    target: Targets = typer.Option(
        Targets.developer, help="choose runtime or developer target"
    ),
    image: str = typer.Option("", help="override container image to use"),
    tag: Optional[str] = typer.Option(None, help="override image tag to use."),
    args: str = typer.Option(
        "", help=f"Additional args for {DOCKER}/docker, 'must be quoted'"
    ),
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
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
    values = ioc_folder / "values.yaml"
    if not values.exists():
        typer.echo(f"values.yaml not found in {ioc_folder}")
        raise typer.Exit(1)
    mounts.append(f"-v {ioc_folder}/{CONFIG_FOLDER}:{IOC_CONFIG_FOLDER}")

    values_text = values.read_text()
    matches = re.findall(r"image: (.*):(.*)", values_text)
    if len(matches) == 1:
        tag = tag or matches[0][1]
        image = matches[0][0] + f":{tag}"
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
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
    ),
):
    """
    Stop a running local IOC container
    """
    run_command(f"{DOCKER} stop -t0 {ioc_name}", error_OK=True)


@dev.command()
def exec(
    ctx: typer.Context,
    command: str = typer.Argument(
        "bash", help="command to execute inside the container must be 'single quoted'"
    ),
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
    ),
):
    """
    Execute a command inside a running local IOC container
    """
    run_command(f'{DOCKER} exec -it {ioc_name} bash -c "{command}"')


@dev.command()
def wait_pv(
    ctx: typer.Context,
    pv_name: str = typer.Argument(
        ..., help="A PV to check in order to confirm the IOC is running"
    ),
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
    ),
):
    """
    Execute a command inside a running local IOC container
    """
    for i in range(5):
        result = run_command(
            f'{DOCKER} exec -it {ioc_name} bash -c "caget {pv_name}"', interactive=False
        )
        if "connect timed" not in str(result):
            break
    else:
        typer.echo(f"PV {pv_name} not found in {ioc_name}")
        raise typer.Exit(1)


@dev.command()
def build(
    ctx: typer.Context,
    folder: Path = typer.Option(Path("."), help="Container project folder"),
    tag: str = typer.Option(IMAGE_TAG, help="version tag for the image"),
    arch: Architecture = typer.Option(
        Architecture.linux, help="choose target architecture"
    ),
    platform: str = typer.Option("linux/amd64", help="target platform"),
    cache: bool = typer.Option(True, help="use --no-cache to do a clean build"),
    buildx: bool = typer.Option(False, help="Use buildx if available"),
    cache_to: Optional[Path] = typer.Option(None, help="buildx cache to folder"),
    cache_from: Optional[Path] = typer.Option(None, help="buildx cache from folder"),
    push: bool = typer.Option(False, help="buildx push to registry"),
):
    """
    Build a generic IOC container locally from a container project.

    Builds both developer and runtime targets.
    """
    repo, _ = get_git_name(folder, full=True)

    args = f" --platform {platform}"
    if buildx and DOCKER == DOCKER_PATH:
        cmd = f"{DOCKER} buildx"
        run_command(f"{cmd} create --driver docker-container --use", interactive=False)
        args += f" --cache-from=type=local,src={cache_from}" if cache_from else ""
        args += f" --cache-to=type=local,dest=${cache_to},mode=max" if cache_to else ""
        args += " --push" if push else " --load "
    else:
        cmd = f"{DOCKER}"

    for target in Targets:
        image = get_image_name(repo, arch, target)
        image_name = f"{image}:{tag} " f"{'--no-cache' if not cache else ''}"
        run_command(
            f"{cmd} build --target {target} --build-arg TARGET_ARCHITECTURE={arch}"
            f"{args} -t {image_name} {folder}"
        )
