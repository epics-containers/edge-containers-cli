import os
import subprocess
from typing import Optional

import typer

from .logging import log

K8S_HELM_REGISTRY: Optional[str] = ""
DOCKER_CMD: Optional[str] = ""
HELM_CMD: Optional[str] = ""
K8S_BEAMLINE: Optional[str] = ""


def run_command(command: str, error_OK=False) -> Optional[str]:
    """Run a command and return the output"""

    result = subprocess.run(command.split(), capture_output=True)

    if result.returncode == 0:
        return str(result.stdout.decode("utf-8")).strip()
    elif error_OK:
        return None
    else:
        typer.echo(f"Command failed: {command} {result.stderr.decode('utf-8')}")
        raise typer.Exit(1)


def check_beamline(beamline: Optional[str]):
    if beamline is None and K8S_BEAMLINE is None:
        typer.echo("Please set K8S_BEAMLINE or pass --beamline")
        raise typer.Exit(1)
    else:
        global K8S_BEAMLINE
        K8S_BEAMLINE = beamline


def check_docker():
    if DOCKER_CMD is None:
        typer.echo("This command requires docker or podman, neither were found")
        raise typer.Exit(1)


def check_helm(registry: Optional[str]):
    if HELM_CMD is None:
        typer.echo("This command requires helm, helm not found")
        raise typer.Exit(1)
    elif registry is None and K8S_HELM_REGISTRY is None:
        typer.echo("Please set K8S_HELM_REGISTRY or pass --helm-registry")
        raise typer.Exit(1)


def check_tools():

    global K8S_HELM_REGISTRY, DOCKER_CMD, HELM_CMD, K8S_BEAMLINE

    K8S_HELM_REGISTRY = os.environ.get("K8S_HELM_REGISTRY", None)
    K8S_BEAMLINE = os.environ.get("K8S_BEAMLINE", None)

    DOCKER_CMD = run_command("which podman", error_OK=True)
    if DOCKER_CMD is None:
        DOCKER_CMD = run_command("which docker", error_OK=True)

    HELM_CMD = run_command("which helm", error_OK=True)

    log.info("DOCKER_CMD=%s", DOCKER_CMD)
    log.info("HELM_CMD=%s", HELM_CMD)
