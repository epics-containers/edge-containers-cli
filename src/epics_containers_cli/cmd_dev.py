import os
from pathlib import Path
from typing import Optional

import typer

from .logging import log
from .shell import K8S_IMAGE_REGISTRY, check_git, check_image, run_command

dev = typer.Typer()  # for nested sub commands of 'dev'

IMAGE_TAG = "work"
REPOS_FOLDER = "{folder}/repos"

# parameters for container launches
REPOS = f"-v {REPOS_FOLDER}:/repos"
ENVIRON = "-e DISPLAY -e USER -e SHELL"
OPTS = "--security-opt=label=type:container_runtime_t"
VOLUMES = (
    " -v=/tmp:/tmp"
    " -v=/home/{USER}:/home/{USER}"
    " -v=/home/{USER}/.bashrc_dev:/root/.bashrc"
    " -v=/home/{USER}/.inputrc:/root/.inputrc"
    " -v=/scratch:/scratch"
)
VOLUMES = VOLUMES.format(USER=os.environ.get("USER"))
ALL_PARAMS = f"{ENVIRON} {VOLUMES} {OPTS} {REPOS}"


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
    print(f"syncing container folder /repos to host folder {repos}")
    repos.mkdir(parents=True, exist_ok=True)
    run_command(
        f"podman run --rm {OPTS} -v {repos}:/copy {image}:{IMAGE_TAG} "
        f"rsync -a /repos/ /copy",
        interactive=True,
        show_cmd=True,
    )


@dev.command()
def launch(
    folder: Path = typer.Argument(
        Path("."), help="generic IOC container project folder"
    ),
    config: Optional[Path] = typer.Argument(None, help="IOC instance config folder"),
    start: bool = typer.Option(True, help="Set to true to launch the IOC"),
    image_registry: Optional[str] = typer.Option(
        K8S_IMAGE_REGISTRY, help="Image registry to pull from"
    ),
):
    """Launch a generic IOC container"""

    repo = check_git(folder)
    image = check_image(repo, image_registry)

    params = ALL_PARAMS.format(folder=folder.absolute())

    prepare(folder, image_registry)

    run_command(f"podman rm -ft0 {repo}", show_cmd=True)
    run_command(
        f"podman run -it --name {repo} {params} {image}:{IMAGE_TAG} bash",
        show_cmd=True,
        interactive=True,
    )


@dev.command()
def build(
    folder: Path = typer.Option(Path("."), help="IOC project folder"),
):
    """Build a generic IOC container image"""


@dev.command()
def debug_build():
    """Launches a container with the most recent image build.
    Useful for debugging failed builds"""
    log.info("debugging last build")


@dev.command()
def make(
    target: str = typer.Option(
        None,
        help="IOC project folder",
    ),
):
    """make the generic IOC source code inside its container"""
