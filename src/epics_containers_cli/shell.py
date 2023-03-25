"""
functions for executing commands and querying environment in the linux shell
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import ruamel.yaml as yaml
import typer
from rich import print

from .enums import Architecture
from .logging import log


def beamline_str() -> Optional[str]:
    """convert BEAMLINE of the form i16 to a K8S_DOMAIN form bl16i"""

    parts = re.compile(r"([a-z])(\d\d)")

    if BEAMLINE:
        match = parts.match(BEAMLINE)
        if match:
            return f"bl{match.group(2).zfill(2)}{match.group(1).lower()}"

    return None


BEAMLINE = os.environ.get("BEAMLINE", None)
K8S_HELM_REGISTRY = os.environ.get("K8S_HELM_REGISTRY", None)
K8S_HELM_ROOT = os.environ.get("K8S_HELM_REGISTRY", None)
K8S_IMAGE_REGISTRY = os.environ.get("K8S_IMAGE_REGISTRY", None)
K8S_LOG_URL = os.environ.get("K8S_LOG_URL", None)
K8S_QUIET = os.environ.get("K8S_QUIET", None)
K8S_DOMAIN = os.environ.get("K8S_DOMAIN", None) or beamline_str()
if os.environ.get("K8S_HELM_REGISTRY_ADD_DOMAIN", False) is not False:
    K8S_HELM_REGISTRY = f"{K8S_HELM_REGISTRY}/{K8S_DOMAIN}"

ERROR = """
[bold red]Command failed: [/bold red][gray37]{0}[/gray37]
{1}"""


def run_command(
    command: str,
    error_OK=False,
    show=False,
    show_cmd=False,
    interactive=False,
    shell=True,
) -> Optional[str]:
    """Run a command and return the output"""

    if show_cmd:
        print(f"[gray37]{command}[/gray37]")

    if not shell:
        commands = command.split()
    else:
        commands = [command]

    result = subprocess.run(commands, capture_output=not interactive, shell=shell)

    if interactive:
        if result.returncode != 0 and not error_OK:
            raise typer.Exit(1)
        return None
    else:
        if result.returncode == 0:
            if show:
                typer.echo(result.stdout.decode("utf-8"))
            return result.stdout.decode("utf-8").strip()
        elif error_OK:
            return None
        else:
            if show:
                command = ""  # don't repeat the command
            print(ERROR.format(command, result.stderr.decode("utf-8")))
            raise typer.Exit(1)


def check_ioc(ioc_name: str, bl: str):
    if not run_command(f"kubectl get -n {bl} deploy/{ioc_name}", error_OK=True):
        print(f"ioc {ioc_name} does not exist in domain {bl}")
        raise typer.Exit(1)


def check_domain(domain: str):
    if not run_command(f"kubectl get namespace {domain} -o name", error_OK=True):
        print(f"domain {domain} does not exist")
        raise typer.Exit(1)

    log.info("domain = %s", domain)


def get_image_name(
    repo_name: str, registry, arch: Architecture = Architecture.linux
) -> str:
    image = f"{registry}/{repo_name}-{arch}-developer"
    log.info("image  = %s", image)
    return image


def get_git_name(folder: Path = Path(".")) -> str:
    if not folder.joinpath(".git").exists():
        print(f"folder {folder.absolute()} is not a git repository")
        raise typer.Exit(1)

    os.chdir(folder)
    remotes = str(run_command("git remote -v"))
    log.debug(f"remotes = {remotes}")

    matches = re.findall(r"\/(.*)\.git", remotes)
    if len(matches) > 0:
        repo_basename = matches[0]
    else:
        print(f"folder {folder.absolute()} cannot get repo name")
        raise typer.Exit(1)

    return repo_basename


def get_helm_chart(folder: Path) -> Tuple[str, str]:
    # verify this is a helm chart and extract the IOC name from it
    with open(folder / "Chart.yaml", "r") as stream:
        chart = yaml.safe_load(stream)

    domain_chart_loc = ""
    for dep in chart["dependencies"]:
        if dep["name"] == "beamline-chart":
            domain_chart_loc = dep["repository"]
            break

    if not domain_chart_loc:
        print("invalid Chart.yaml. Can't find domain chart dependency")
        raise typer.Exit(1)

    domain_values_yaml = folder / domain_chart_loc[7:] / "values.yaml"

    # this would allow us to read information from the beamline default
    # values - but we have dropped the requirement to supply domain / beamline
    # in the yaml so it can be overriden by helm.
    with open(domain_values_yaml, "r") as stream:
        _ = yaml.safe_load(stream)

    with open(folder / "values.yaml", "r") as stream:
        ioc_values = yaml.safe_load(stream)

    ioc_name = chart["name"]
    generic_image = ioc_values["base_image"]

    return ioc_name, generic_image
