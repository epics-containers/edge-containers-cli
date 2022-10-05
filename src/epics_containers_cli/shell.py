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

from .logging import log

K8S_BEAMLINE = os.environ.get("K8S_BEAMLINE", None)
K8S_HELM_REGISTRY = os.environ.get("K8S_HELM_REGISTRY", None)
K8S_IMAGE_REGISTRY = os.environ.get("K8S_IMAGE_REGISTRY", None)
K8S_GRAYLOG_URL = os.environ.get("K8S_GRAYLOG_URL", None)
K8S_QUIET = os.environ.get("K8S_QUIET", None)

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
        print(f"ioc {ioc_name} does not exist in beamline {bl}")
        raise typer.Exit(1)


def check_beamline(beamline: Optional[str]) -> str:
    if beamline is None:
        beamline = K8S_BEAMLINE
    if beamline is None:
        print("Please set K8S_BEAMLINE or pass --beamline")
        raise typer.Exit(1)

    if not run_command(f"kubectl get namespace {beamline} -o name", error_OK=True):
        print(f"beamline {beamline} does not exist")
        raise typer.Exit(1)

    log.info("beamline = %s", beamline)
    return beamline


def check_docker():
    docker_cmd = run_command("which podman", error_OK=True)
    if docker_cmd is None:
        docker_cmd = run_command("which docker", error_OK=True)

    if docker_cmd is None:
        print("This command requires docker or podman, neither were found")
        raise typer.Exit(1)

    log.info("docker command = %s", docker_cmd)


def check_kubectl():
    kube_cmd = run_command("which kubectl", error_OK=True)

    if kube_cmd is None:
        print("This command requires kubectl, kubectl not found")
        raise typer.Exit(1)

    log.info("kubectl command = %s", kube_cmd)


def check_helm(registry: Optional[str] = None, local=False):
    helm_cmd = run_command("which helm", error_OK=True)

    if helm_cmd is None:
        print("This command requires helm, helm not found")
        raise typer.Exit(1)

    if not local:
        if registry is None:
            registry = K8S_HELM_REGISTRY
        if registry is None:
            print("Please set K8S_HELM_REGISTRY or pass --helm-registry")
            raise typer.Exit(1)

    log.info("helm command = %s", helm_cmd)
    log.info("helm registry = %s", registry)
    return registry


def check_image(repo_name: str, registry: Optional[str] = None) -> str:
    if registry is None:
        registry = K8S_HELM_REGISTRY
    if registry is None:
        print("Please set K8S_image_REGISTRY or pass --image-registry")
        raise typer.Exit(1)

    image = f"{registry}/{repo_name}-linux-developer"
    log.info("image  = %s", image)
    return image


def check_git(folder: Path = Path(".")) -> str:
    git_cmd = run_command("which git", error_OK=True)

    if git_cmd is None:
        print("This command requires git, git not found")
        raise typer.Exit(1)

    log.info("git command = %s", git_cmd)

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


def check_helm_chart(folder: Path) -> Tuple[str, str, str]:
    # verify this is a helm chart and extract the IOC name from it
    with open(folder / "Chart.yaml", "r") as stream:
        chart = yaml.safe_load(stream)

    bl_chart_loc = ""
    for dep in chart["dependencies"]:
        if dep["name"] == "beamline-chart":
            bl_chart_loc = dep["repository"]
            break

    if not bl_chart_loc:
        print("invalid Chart.yaml. Can't find beamline chart dependency")
        raise typer.Exit(1)

    bl_values_yaml = folder / bl_chart_loc[7:] / "values.yaml"

    with open(bl_values_yaml, "r") as stream:
        bl_values = yaml.safe_load(stream)

    with open(folder / "values.yaml", "r") as stream:
        ioc_values = yaml.safe_load(stream)

    namespace = bl_values["exports"]["beamline_defaults"]["namespace"]
    ioc_name = chart["name"]
    generic_image = ioc_values["base_image"]

    return namespace, ioc_name, generic_image
