"""
functions for executing commands and querying environment in the linux shell
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import typer

from .enums import Architecture
from .logging import log

EC_EPICS_DOMAIN = os.environ.get("EC_EPICS_DOMAIN") or os.environ.get("BEAMLINE")
EC_DOMAIN_REPO = os.environ.get("EC_DOMAIN_REPO")
EC_REGISTRY_MAPPING = os.environ.get("EC_REGISTRY_MAPPING", "github.com=ghcr.io")
EC_K8S_NAMESPACE = os.environ.get("EC_K8S_NAMESPACE", None) or EC_EPICS_DOMAIN
EC_LOG_URL = os.environ.get("EC_LOG_URL", None)


def run_command(command: str, interactive=True, error_OK=False) -> Optional[str]:
    """
    Run a command and return the output
    """

    result = subprocess.run(command, capture_output=not interactive, shell=True)

    if not interactive:
        typer.echo(result.stdout.decode())

    if result.returncode != 0 and not error_OK:
        typer.echo(result.stderr.decode())
        raise typer.Exit(1)

    if not interactive:
        return result.stdout.decode()


def check_ioc(ioc_name: str, bl: str):
    if not run_command(f"kubectl get -n {bl} deploy/{ioc_name}", error_OK=True):
        typer.echo(f"ioc {ioc_name} does not exist in domain {bl}")
        raise typer.Exit(1)


def check_domain(domain: str):
    if not run_command(f"kubectl get namespace {domain} -o name", error_OK=True):
        typer.echo(f"domain {domain} does not exist")
        raise typer.Exit(1)

    log.info("domain = %s", domain)


def get_image_name(
    repo: str, arch: Architecture = Architecture.linux, target: str = "developer"
) -> str:
    registry = repo2registry(repo).lower()
    image = f"{registry}-{arch}-{target}"
    log.info("repo = %s image  = %s", repo, image)
    return image


def get_git_name(folder: Path = Path("."), full: bool = False) -> str:
    if not folder.joinpath(".git").exists():
        typer.echo(f"folder {folder.absolute()} is not a git repository")
        raise typer.Exit(1)

    os.chdir(folder)
    remotes = str(run_command("git remote -v"))
    log.debug(f"remotes = {remotes}")

    if full:
        matches = re.findall(r"(git@.*(?:\.git)?) ", remotes)
    else:
        matches = re.findall(r"\/(.*)(?:\.git)? ", remotes)

    if len(matches) > 0:
        repo_name = matches[0]
    else:
        typer.echo(f"folder {folder.absolute()} cannot get repo name")
        raise typer.Exit(1)

    return repo_name


# work out what the registry name is for a given repo remote e.g.
def repo2registry(repo_name: str) -> str:
    """convert a repo name to a registry name"""

    match = re.match(r"git@([^:]*):(.*)\/(.*)(?:.git)?", repo_name)
    if not match:
        typer.echo(f"repo {repo_name} is not a valid git remote")
        raise typer.Exit(1)

    source_reg, org, repo = match.groups()
    log.debug("source_reg = %s org = %s repo = %s", source_reg, org, repo)

    for mapping in EC_REGISTRY_MAPPING.split():
        if mapping.split("=")[0] == source_reg:
            registry = mapping.split("=")[1]
            registry = f"{registry}/{org}/{repo}"
            break
    else:
        typer.echo(f"repo {repo_name} does not match any registry mapping")
        typer.echo("please update the environment variable IMAGE_REGISTRY_MAPPING")
        raise typer.Exit(1)

    return registry
