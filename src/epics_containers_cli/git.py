"""
Utility functions for working with git
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.globals import Architecture
from epics_containers_cli.logging import log
from epics_containers_cli.shell import (
    check_beamline_repo,
    run_command,
)


def get_image_name(
    repo: str,
    arch: Architecture = Architecture.linux,
    target: str = "developer",
    suffix: Optional[str] = None,
) -> str:
    if suffix is None:
        suffix = "-{arch}-{target}"
    registry = repo2registry(repo).lower()
    img_suffix = suffix.format(repo=repo, arch=arch, target=target, registry=registry)

    image = f"{registry}{img_suffix}"
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

    # First try matching using the regex mappings environment variable
    registry = ""
    # remove .git suffix because regexes are hard to make with optional suffix
    # not all git remotes have it for some reason
    repo_name = repo_name.removesuffix(".git")

    for mapping in glob_vars.EC_REGISTRY_MAPPING_REGEX.split("\n"):
        if mapping == "":
            continue
        regex, replacement = mapping.split(" ")
        log.debug("regex = %s replacement = %s", regex, replacement)
        match = re.match(regex, repo_name)
        if match is not None:
            registry = match.expand(replacement)
            break

    if registry:
        return registry

    # Now try matching using the simple mappings environment variable.
    # Here automatically add the organization name to the image root URL
    log.debug("extracting fields from repo name %s", repo_name)

    match_git = re.match(r"git@([^:]*):(.*)\/(.*)", repo_name)
    match_http = re.match(r"https:\/\/([^\/]*)\/([^\/]*)\/([^\/]*)", repo_name)
    for match in [match_git, match_http]:
        if match is not None:
            source_reg, org, repo = match.groups()
            break
    else:
        log.error(f"repo {repo_name} is not a valid git remote")
        raise typer.Exit(1)

    log.debug("source_reg = %s org = %s repo = %s", source_reg, org, repo)

    for mapping in glob_vars.EC_REGISTRY_MAPPING.split():
        if mapping.split("=")[0] == source_reg:
            registry = mapping.split("=")[1]
            registry = f"{registry}/{org}/{repo}"
            break
    else:
        log.error(f"repo {repo_name} does not match any registry mapping")
        log.error("please update the environment variable EC_REGISTRY_MAPPING")
        raise typer.Exit(1)

    return registry


def versions(beamline_repo: str, ioc_name: str, folder: Path):
    """
    determine the versions of an IOC instance by discovering the tags in the
    beamline repo at which changes to the instance were made since the last
    tag
    """
    check_beamline_repo(beamline_repo)
    typer.echo(f"Available instance versions for {ioc_name}:")

    run_command(f"git clone {beamline_repo} {folder}", interactive=False)

    ioc_name = Path(ioc_name).name
    os.chdir(folder)
    result = str(run_command("git tag", interactive=False))
    log.debug(f"checking these tags for changes in the instance: {result}")

    count = 0
    tags = result.split("\n")
    for tag in tags:
        if tag == "":
            continue
        cmd = f"git diff --name-only {tag} {tag}^"
        result = str(run_command(cmd, interactive=False))

        if ioc_name in result:
            typer.echo(f"  {tag}")
            count += 1

    if count == 0:
        # also look to see if the first tag was when the instance was created
        cmd = f"git diff --name-only {tags[0]} $(git hash-object -t tree /dev/null)"
        result = str(run_command(cmd, interactive=False))
        if ioc_name in result:
            typer.echo(f"  {tags[0]}")
