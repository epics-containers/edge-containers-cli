import re
from pathlib import Path
from typing import Optional

import typer

from .shell import (
    K8S_IMAGE_REGISTRY,
    check_git,
    check_helm_chart,
    check_image,
    run_command,
)

dev = typer.Typer()

IMAGE_TAG = "work"
REPOS_FOLDER = "{folder}/repos"

# parameters for container launches
REPOS = f" -v {REPOS_FOLDER}:/repos "
ENVIRON = "-e DISPLAY -e USER -e SHELL"
OPTS = "--security-opt=label=type:container_runtime_t"
VOLUMES = (
    " -v=/tmp:/tmp"
    " -v=/home/$USER:/home/$USER"
    " -v=/home/$USER/.bashrc_dev:/root/.bashrc"
    " -v=/home/$USER/.inputrc:/root/.inputrc"
    " -v=/scratch:/scratch"
)
ALL_PARAMS = f"{ENVIRON} {VOLUMES} {OPTS}"


def prepare(folder: Path, registry: Optional[str]):
    """
    Prepare a generic IOC project folder for launching

    1st make sure that the container image is present and tagged "work"
    2nd extract the contents of repos to a local folder
    """
    repo = check_git(folder)
    image = check_image(repo, registry)
    repos = Path(REPOS_FOLDER.format(folder=folder.absolute()))

    # make sure the image with tag "work" is present
    if run_command("podman images -q {image}:{IMAGE_TAG}", error_OK=True):
        print(f"Image {image}:{IMAGE_TAG} not found, pulling ...")

        run_command(f"podman pull {image}:main", interactive=True, show_cmd=True)
        run_command(
            f"podman tag {image}:main {image}:{IMAGE_TAG}",
            interactive=True,
            show_cmd=True,
        )

    # rsync the repos folder to the local folder
    if not repos.exists():
        print(f"syncing container folder /repos to host folder {repos}")
        repos.mkdir(parents=True)
        run_command(
            f"podman run --rm {OPTS} -v {repos}:/copy {image}:{IMAGE_TAG} "
            f"rsync -a /repos/ /copy",
            interactive=True,
            show_cmd=True,
        )


@dev.command()
def launch(
    folder: Path = typer.Argument(Path("."), help="container project folder"),
    image_registry: Optional[str] = typer.Option(
        K8S_IMAGE_REGISTRY, help="Image registry to pull from"
    ),
):
    """Launch a bash prompt in a container"""

    repo = check_git(folder)
    image = check_image(repo, image_registry)

    params = ALL_PARAMS + REPOS.format(folder=folder.absolute())

    prepare(folder, image_registry)

    run_command(f"podman rm -ft0 {repo}", show_cmd=True)
    run_command(
        f"podman run -it --name {repo} {params} {image}:{IMAGE_TAG} bash",
        show_cmd=True,
        interactive=True,
    )


@dev.command()
def ioc_launch(
    helm_chart: Path = typer.Argument(..., help="root folder of local ioc helm chart"),
    folder: Optional[Path] = typer.Argument(
        None, help="folder for generic IOC project"
    ),
    tag: str = typer.Option(IMAGE_TAG, help="version of the generic IOC to use"),
    image_registry: Optional[str] = typer.Option(
        K8S_IMAGE_REGISTRY, help="Image registry to pull from"
    ),
    debug: bool = typer.Option(False, help="start a remote debug session"),
):
    """Launch an IOC instance using a local helm chart definition.
    Set folder for a locally editable generic IOC or tag to choose any
    version from the registry."""

    if tag == IMAGE_TAG and folder is None:
        print(
            "You must specify a version tag for the generic IOC\n"
            "or a folder with a local clone of the generic IOC project"
        )
        raise (typer.Exit(1))

    bl, ioc_name, image = check_helm_chart(helm_chart)
    # switch to the developer target and requested tag for generic IOC image
    image = re.findall(r"[^:]*", image)[0].replace("runtime", "developer")

    # make sure there are not 2 copies running
    run_command(f"podman rm -ft0 {ioc_name}", show_cmd=True)

    helm_chart = helm_chart.absolute()
    config_folder = "/repos/epics/ioc/config"
    config = f'-v {helm_chart / "config"}:{config_folder}'

    if folder is None:
        # launch the requested version of the generic IOC only
        run_command(
            f"podman run -it --name {ioc_name} {config} {ALL_PARAMS} {image}:{tag} "
            f"bash {config_folder}/start.sh",
            show_cmd=True,
            interactive=True,
        )
    else:
        # launch the local work version of the generic IOC with locally mounted
        # /repos folder - useful for testing changes to repos folder
        repos = REPOS.format(folder=folder.absolute())
        command = (
            f"bash {config_folder}/start.sh; "
            f"echo IOC EXITED - hit ctrl D to leave IOC container; "
            f"bash"
        )
        run_command(
            f"podman run -it --name {ioc_name} {repos} {config} {ALL_PARAMS}"
            f" {image}:{IMAGE_TAG} bash -c '{command}'",
            show_cmd=True,
            interactive=True,
        )

    # TODO look into debugging


def build(
    folder: Path = typer.Option(Path("."), help="Container project folder"),
):
    """Build a container image"""


@dev.command()
def debug_build():
    """Launches a container with the most recent image build.
    Useful for debugging failed builds"""


@dev.command()
def build():
    """Build a container locally from a container project."""


@dev.command()
def make(
    folder: Path = typer.Option(Path("."), help="IOC project folder"),
    image_registry: Optional[str] = typer.Option(
        K8S_IMAGE_REGISTRY, help="Image registry to pull from"
    ),
):
    """make the generic IOC source code inside its container"""

    repo = check_git(folder)
    image = check_image(repo, image_registry)

    params = ALL_PARAMS + REPOS.format(folder=folder.absolute())
    container_name = f"build-{repo}"

    prepare(folder, image_registry)

    command = (
        "cd /repos/epics/support && "
        "python module.py dependencies && "
        "make && "
        "cd /repos/epics/ioc && "
        "make; "
        "echo; echo BUILD DONE - hit ctrl-D to exit the build container.; "
        "bash"
    )

    # make sure we dont run > 1 build at a time
    run_command(f"podman rm -ft0 {container_name}")

    run_command(
        f"podman run --rm --name {container_name} -it {params} "
        f"{image}:{IMAGE_TAG} bash -c '{command}'",
        show_cmd=True,
        interactive=True,
    )
