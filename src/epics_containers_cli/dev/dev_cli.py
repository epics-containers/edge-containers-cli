from pathlib import Path
from typing import Optional

import typer

from epics_containers_cli.dev.dev_commands import DevCommands

from ..globals import (
    IOC_NAME,
    IOC_START,
    Architecture,
    Targets,
)

dev = typer.Typer()

IMAGE_TAG = "local"
MOUNTED_FILES = ["/.bashrc", "/.inputrc", "/.bash_eternal_history"]

# parameters for container launches
PODMAN_OPT = "--security-opt=label=type:container_runtime_t"
# NOTE: I have removed --net host so that tested IOCs are isolated
# TODO: review this choice when implementing GUIs


@dev.command()
def launch_local(
    ctx: typer.Context,
    ioc_instance: Optional[Path] = typer.Argument(
        None,
        help="local IOC instance config folder",
        dir_okay=True,
        file_okay=False,
        exists=True,
    ),
    generic_ioc: Path = typer.Option(
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
        "", help="Additional args for podman/docker, 'must be quoted'"
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
    DevCommands().launch_local(
        ioc_instance=ioc_instance,
        generic_ioc=generic_ioc,
        execute=execute,
        target=target,
        tag=tag,
        args=args,
        ioc_name=ioc_name,
    )


@dev.command()
def launch(
    ctx: typer.Context,
    ioc_instance: Path = typer.Argument(
        ...,
        help="local IOC definition folder from domain repo",
        file_okay=False,
        exists=True,
        resolve_path=True,
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
        "", help="Additional args for podman/docker, 'must be quoted'"
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
    DevCommands().launch(
        ioc_instance=ioc_instance,
        execute=execute,
        target=target,
        image=image,
        tag=tag,
        args=args,
        ioc_name=ioc_name,
    )


@dev.command()
def debug_last(
    generic_ioc: Path = typer.Argument(
        Path("."), help="Container project folder", exists=True, file_okay=False
    ),
    mount_repos: bool = typer.Option(
        True, help="Mount generic IOC repo folder into the container"
    ),
):
    """
    Launches a container with the most recent image build.
    Useful for debugging failed builds - if the last build failed it will
    start the container after the most recent successful build step.
    """
    DevCommands().debug_last(generic_ioc=generic_ioc, mount_repos=mount_repos)


@dev.command()
def versions(
    ctx: typer.Context,
    generic_ioc: Path = typer.Argument(
        Path("."), help="Generic IOC project folder", exists=True, file_okay=False
    ),
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
    DevCommands().versions(generic_ioc=generic_ioc, arch=arch, image=image)


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
    DevCommands().stop(ioc_name=ioc_name)


@dev.command()
def exec(
    ctx: typer.Context,
    command: str = typer.Argument(
        "bash", help="command to execute inside the container must be 'single quoted'"
    ),
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
    ),
    args: str = typer.Option("", help="Additional args for exec, 'must be quoted'"),
):
    """
    Execute a command inside a running local IOC container
    """
    DevCommands().exec(ioc_name=ioc_name, command=command, args=args)


@dev.command()
def wait_pv(
    ctx: typer.Context,
    pv_name: str = typer.Argument(
        ..., help="A PV to check in order to confirm the IOC is running"
    ),
    ioc_name: str = typer.Option(
        IOC_NAME, help="container name override. Use to run multiple instances"
    ),
    attempts: int = typer.Option(5, help="no. retries checking for PV"),
):
    """
    Execute a command inside a running local IOC container
    """
    DevCommands().wait_pv(pv_name=pv_name, ioc_name=ioc_name, attempts=attempts)


@dev.command()
def build(
    ctx: typer.Context,
    generic_ioc: Path = typer.Option(
        Path("."), help="Generic IOC project folder", exists=True, file_okay=False
    ),
    tag: str = typer.Option(IMAGE_TAG, help="version tag for the image"),
    arch: Architecture = typer.Option(
        Architecture.linux, help="choose target architecture"
    ),
    platform: str = typer.Option("linux/amd64", help="target platform"),
    cache: bool = typer.Option(True, help="use --no-cache to do a clean build"),
    cache_to: Optional[str] = typer.Option(None, help="buildx cache to folder"),
    cache_from: Optional[str] = typer.Option(None, help="buildx cache from folder"),
    push: bool = typer.Option(False, help="buildx push to registry"),
    rebuild: bool = typer.Option(True, help="rebuild the image even if it exists"),
    target: Optional[str] = typer.Option(
        None, help="target to build (default: developer and runtime)"
    ),
    suffix: Optional[str] = typer.Option(None, help="suffix for image"),
):
    """
    Build a generic IOC container locally from a container project.

    Builds both developer and runtime targets.
    """
    DevCommands().build(
        generic_ioc=generic_ioc,
        tag=tag,
        arch=arch,
        platform=platform,
        cache=cache,
        cache_from=cache_from,
        cache_to=cache_to,
        push=push,
        rebuild=rebuild,
        target=target,
        suffix=suffix,
    )
