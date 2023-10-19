import os
import re
from pathlib import Path
from typing import Optional, Tuple

import typer

from epics_containers_cli.logging import log
from epics_containers_cli.shell import EC_REGISTRY_MAPPING, run_command

from .globals import CONFIG_FOLDER, Architecture


def get_instance_image_name(ioc_instance: Path, tag: Optional[str] = None) -> str:
    ioc_instance = ioc_instance.resolve()
    values = ioc_instance / "values.yaml"
    if not values.exists():
        log.error(f"values.yaml not found in {ioc_instance}")
        raise typer.Exit(1)

    values_text = values.read_text()
    matches = re.findall(r"image: (.*):(.*)", values_text)
    if len(matches) == 1:
        tag = tag or matches[0][1]
        image = matches[0][0] + f":{tag}"
    else:
        log.error(f"image tag definition not found in {values}")
        raise typer.Exit(1)

    return image


def get_image_name(
    repo: str, arch: Architecture = Architecture.linux, target: str = "developer"
) -> str:
    registry = repo2registry(repo).lower().removesuffix(".git")

    image = f"{registry}-{arch}-{target}"
    log.info("repo = %s image  = %s", repo, image)
    return image


def get_git_name(folder: Path = Path(".")) -> Tuple[str, Path]:
    """
    work out the git repo name and top level folder for a local clone
    """
    os.chdir(folder)
    path = str(run_command("git rev-parse --show-toplevel", interactive=False))
    git_root = Path(path.strip())

    remotes = str(run_command("git remote -v", interactive=False))
    log.debug(f"remotes = {remotes}")

    matches = re.findall(r"((?:(?:git@)|(?:http[s]+:\/\/)).*) (?:.fetch.)", remotes)

    if len(matches) > 0:
        repo_name = str(matches[0])
    else:
        log.error(f"folder {folder.absolute()} cannot parse repo name {remotes}")
        raise typer.Exit(1)

    log.debug(f"repo_name = {repo_name}, git_root = {git_root}")
    return repo_name, git_root


# work out what the registry name is for a given repo remote e.g.
def repo2registry(repo_name: str) -> str:
    """convert a repo name to the related a container registry name"""

    log.debug("extracting fields from repo name %s", repo_name)

    match_git = re.match(r"git@([^:]*):(.*)\/(.*)(?:.git)", repo_name)
    match_http = re.match(r"https:\/\/([^\/]*)\/([^\/]*)\/([^\/]*)", repo_name)
    for match in [match_git, match_http]:
        if match is not None:
            source_reg, org, repo = match.groups()
            break
    else:
        log.error(f"repo {repo_name} is not a valid git remote")
        raise typer.Exit(1)

    log.debug("source_reg = %s org = %s repo = %s", source_reg, org, repo)

    if not EC_REGISTRY_MAPPING:
        log.error("environment variable EC_REGISTRY_MAPPING not set")
        raise typer.Exit(1)

    for mapping in EC_REGISTRY_MAPPING.split():
        if mapping.split("=")[0] == source_reg:
            registry = mapping.split("=")[1]
            registry = f"{registry}/{org}/{repo}"
            break
    else:
        log.error(f"repo {repo_name} does not match any registry mapping")
        log.error("please update the environment variable EC_REGISTRY_MAPPING")
        raise typer.Exit(1)

    return registry


def check_ioc_instance_path(ioc_path: Path, yes: bool = False):
    """
    verify that the ioc instance path is valid
    """
    ioc_path = ioc_path.absolute()
    ioc_name = ioc_path.name.lower()
    if (
        not (ioc_path / "values.yaml").exists()
        or not (ioc_path / CONFIG_FOLDER).is_dir()
    ):
        log.error("ERROR: IOC instance requires values.yaml and config")
        raise typer.Exit(1)

    return ioc_name, ioc_path
