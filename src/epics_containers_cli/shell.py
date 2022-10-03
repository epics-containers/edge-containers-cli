"""
functions for executing commands and querying environment in the linux shell
"""

import os
import subprocess
from typing import Optional

import typer
from rich import print

from .logging import log

K8S_HELM_REGISTRY: Optional[str] = os.environ.get("K8S_HELM_REGISTRY", None)
K8S_BEAMLINE: Optional[str] = os.environ.get("K8S_BEAMLINE", None)

ERROR = """
[bold red]Command failed: [/bold red][gray37]{0}[/gray37]
{1}"""


def run_command(command: str, error_OK=False, show=False) -> Optional[str]:
    """Run a command and return the output"""

    if show:
        print(f"[gray37]{command}[/gray37]")

    result = subprocess.run(command.split(), capture_output=True)

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


def check_ioc(ioc_name: str):
    if str(K8S_BEAMLINE) not in ioc_name:
        print(
            f"IOC {ioc_name} does name does not match beamline {K8S_BEAMLINE}\n"
            "set K8S_BEAMLINE or pass --beamline to match"
        )
        raise typer.Exit(1)


def check_beamline(beamline: Optional[str]):
    global K8S_BEAMLINE
    if beamline is not None:
        K8S_BEAMLINE = beamline
    if K8S_BEAMLINE is None:
        print("Please set K8S_BEAMLINE or pass --beamline")
        raise typer.Exit(1)

    log.info("beamline = %s", K8S_BEAMLINE)


def check_docker() -> str:
    docker_cmd = run_command("which podman", error_OK=True)
    if docker_cmd is None:
        docker_cmd = run_command("which docker", error_OK=True)

    if docker_cmd is None:
        print("This command requires docker or podman, neither were found")
        raise typer.Exit(1)

    log.info("docker command = %s", docker_cmd)
    return docker_cmd


def check_helm(registry: Optional[str]):
    helm_cmd = run_command("which helm", error_OK=True)

    if helm_cmd is None:
        print("This command requires helm, helm not found")
        raise typer.Exit(1)

    if registry is None and K8S_HELM_REGISTRY is None:
        print("Please set K8S_HELM_REGISTRY or pass --helm-registry")
        raise typer.Exit(1)

    log.info("helm command = %s", helm_cmd)
    return helm_cmd
