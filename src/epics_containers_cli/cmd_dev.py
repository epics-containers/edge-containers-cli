import re
import shutil
from os import environ
from pathlib import Path
from typing import Optional

import typer

from .context import Context
from .enums import Architecture
from .shell import get_git_name, get_helm_chart, get_image_name, run_command

dev = typer.Typer()

IMAGE_TAG = "local"
REPOS_FOLDER = "{folder}/repos"
IMAGE_TARGETS = ["developer", "runtime"]

# parameters for container launches
REPOS = f" -v {REPOS_FOLDER}:/repos "
OPTS = "--security-opt=label=type:container_runtime_t --net=host"


def all_params():
    env = "-e DISPLAY -e USER -e SHELL"
    volumes = (
        " -v=/home/$USER:/home/$USER"
        " -v=/home/$USER/.bashrc_dev_container:/root/.bashrc"
        " -v=/home/$USER/.inputrc_container:/root/.inputrc"
        " -v=/home/$USER/.bash_eternal_history:/root/.bash_eternal_history"
    )

    # To make containers in containers nice we need to have some consistency
    # with prompt and history - but we need to get files for that from the
    # host filesystem - hence this slightly ugly logic:

    # copy this container's shell config into the host user's home folder
    # so they can be mounted into the new container
    user = environ["USER"]
    shutil.copyfile("/root/.inputrc", f"/home/{user}/.inputrc_container")
    shutil.copyfile("/root/.bashrc", f"/home/{user}/.bashrc_dev_container")
    # make sure .bash_eternal_history exists
    Path(f"/home/{user}/.bash_eternal_history").touch()

    return f"{env} {volumes} {OPTS}"


def prepare(folder: Path, arch: Architecture = Architecture.linux):
    """
    Prepare a generic IOC project folder for launching

    1st make sure that the container image is present and tagged "work"
    2nd extract the contents of repos to a local folder
    """
    repo = get_git_name(folder, full=True)
    image = get_image_name(repo, arch) + f":{IMAGE_TAG}"
    repos = Path(REPOS_FOLDER.format(folder=folder.absolute()))

    # make sure the image with tag "local" is present
    if run_command(f"podman images -q {image}") == "":
        print(
            f"""
image {image} is not present.
Please run "ec dev build" first.
Or pull the latest built image from the registry and tag it as "{IMAGE_TAG}".
"""
        )
        exit(1)

    # rsync the repos folder to the local folder
    repos.mkdir(parents=True, exist_ok=True)
    run_command(
        f"podman run --rm {OPTS} -v {repos}:/copy "
        # the rsync command refreshes repos but does not overwrite local changes
        f"--entrypoint rsync {image} " f"-au / /copy",
        interactive=True,
        show_cmd=True,
    )

    # overwrite epics/ioc folder with any local changes
    # TODO would this not be better as a mount point?
    run_command(f"rsync -au {folder}/ioc {repos}/epics/", show_cmd=True)

    return image


@dev.command()
def launch(
    ctx: typer.Context,
    folder: Path = typer.Argument(Path("."), help="container project folder"),
    arch: Architecture = typer.Option(
        Architecture.linux, help="choose target architecture"
    ),
    image: Optional[str] = typer.Option(None, help="override container image to use"),
):
    """Launch a bash prompt in a container"""
    repo_name = get_git_name(folder)
    repo = get_git_name(folder, full=True)
    image = image or get_image_name(repo, arch)

    params = all_params() + REPOS.format(folder=folder.absolute())

    prepare(folder, arch)

    run_command(f"podman rm -f {repo_name}", show_cmd=True)
    run_command(
        f"podman run --rm -it --name {repo_name} --entrypoint bash "
        f"{params} {image}:{IMAGE_TAG}",
        show_cmd=True,
        interactive=True,
    )


@dev.command()
def ioc_launch(
    ctx: typer.Context,
    helm_chart: Path = typer.Argument(
        ..., help="root folder of local IOC helm chart", dir_okay=True, file_okay=False
    ),
    folder: Path = typer.Argument(
        None, help="folder for generic IOC project", dir_okay=True, file_okay=False
    ),
    debug: bool = typer.Option(False, help="start a remote debug session"),
):
    """Launch an IOC instance using a local helm chart definition.
    Set folder for a locally editable generic IOC or supply a tag to choose any
    version from the registry."""

    ioc_name, image = get_helm_chart(helm_chart)
    # switch to the developer target and separate the tag for generic IOC image
    match = re.match(r"([^:]*):(.*)$", image)
    if match is None:
        raise ValueError(f"invalid image name in {helm_chart}")

    image = match.group(1).replace("runtime", "developer")
    org_tag = match.group(2)

    # work out which architecture to use for prepare
    arch = Architecture.rtems if "rtems" in image else Architecture.linux

    # make sure there are not 2 copies running
    run_command(f"podman rm -f {ioc_name}", show_cmd=True)

    helm_chart = helm_chart.absolute()
    start_script = "/epics/ioc/start.sh"
    config_folder = "/epics/ioc/config"
    config = f'-v {helm_chart / "config"}:{config_folder}'

    if folder is None:
        # launch generic IOC from the registry with tag specified in helm chart
        run_command(
            f"podman run --rm -it --name {ioc_name} {config} {all_params()}"
            f" {image}:{org_tag} bash {start_script}",
            show_cmd=True,
            interactive=True,
        )
    else:
        # launch the local work version of the generic IOC with locally mounted
        # /repos folder - useful for testing changes to repos folder
        repos = REPOS.format(folder=folder.absolute())

        folder_image = prepare(folder, arch)

        if folder_image != f"{image}:local":
            print(
                f"""
ERROR: the specified Generic IOC image: {folder_image}
does not match the helm chart image: {image}:{org_tag}
you must specify a folder for the local generic IOC project
or a tag for the generic IOC image to use from the registry"""
            )
            raise (typer.Exit(1))

        command = (
            f"bash {start_script}; "
            f"echo IOC EXITED - hit ctrl D to leave IOC container; "
            f"bash"
        )
        run_command(
            f"podman run -it --name {ioc_name} {repos} {config} {all_params()}"
            f" {folder_image} bash -c '{command}'",
            show_cmd=True,
            interactive=True,
        )

    # TODO look into debugging


@dev.command()
def debug_last(
    folder: Path = typer.Argument(Path("."), help="Container project folder"),
    mount_repos: bool = typer.Option(
        True, help="Mount the repos folder into the container"
    ),
):
    """Launches a container with the most recent image build.
    Useful for debugging failed builds"""
    last_image = run_command("podman images | awk '{print $3}' | awk 'NR==2'")

    params = all_params()
    if mount_repos:
        # rsync the state of the container's repos folder to the local folder
        repos = (folder / "repos").absolute()
        repos.mkdir(exist_ok=True)
        run_command(
            f"podman run --rm {OPTS} -v {repos}:/copy {last_image} " "rsync -a / /copy",
            interactive=True,
            show_cmd=True,
        )

        params += f" -v{repos}:/repos "

    run_command(
        f"podman run --rm -it --name debug_build  {params} {last_image}",
        show_cmd=True,
        interactive=True,
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
    """Build a container locally from a container project."""
    repo = get_git_name(folder, full=True)

    for target in IMAGE_TARGETS:
        image = get_image_name(repo, arch, target)
        image_name = f"{image}:{IMAGE_TAG} " f"{'--no-cache' if not cache else ''}"
        run_command(
            f"podman build --target {target} --build-arg TARGET_ARCHITECTURE={arch}"
            f" -t {image_name} {folder}",
            show_cmd=True,
            interactive=True,
        )


@dev.command()
def make(
    ctx: typer.Context,
    folder: Path = typer.Option(Path("."), help="IOC project folder"),
    arch: Architecture = typer.Option(
        Architecture.linux, help="choose target architecture"
    ),
    image: str = typer.Option("", help="override container image to use"),
):
    """make the generic IOC source code inside its container"""

    repo = get_git_name(folder, full=True)
    image = get_image_name(repo, arch)

    params = all_params() + REPOS.format(folder=folder.absolute())
    container_name = f"build-{repo}"

    prepare(folder, arch)

    command = (
        "cd /epics/support && "
        "python modules.py dependencies && "
        "make && "
        "cd /epics/ioc && "
        "make; "
        "echo; echo BUILD DONE - hit ctrl-D to exit the build container.; "
        "bash"
    )

    # make sure we dont run > 1 build at a time
    run_command(f"podman rm -f {container_name}")

    run_command(
        f"podman run --rm --name {container_name} -it {params} "
        f"{image}:{IMAGE_TAG} bash -c '{command}'",
        show_cmd=True,
        interactive=True,
    )


@dev.command()
def versions(
    ctx: typer.Context,
    folder: Path = typer.Option(Path("."), help="IOC project folder"),
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
    c: Context = ctx.obj

    if image == "":
        repo = get_git_name(folder, full=True)
        image = image or get_image_name(repo, arch)

    run_command(
        f"podman run --rm quay.io/skopeo/stable " f"list-tags docker://{image}",
        show=True,
        show_cmd=c.show_cmd,
    )
