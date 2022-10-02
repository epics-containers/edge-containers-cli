import logging
import os
import subprocess
from typing import Optional

import typer

log = logging.getLogger(__name__)

K8S_HELM_REGISTRY: Optional[str] = ""
DOCKER_CMD: Optional[str] = ""
HELM_CMD: Optional[str] = ""


def run_command(command: str, error_OK=False) -> Optional[str]:
    """Run a command and return the output"""

    result = subprocess.run(command.split(), capture_output=True)

    if result.returncode == 0:
        return str(result.stdout.decode("utf-8")).strip()
    elif error_OK:
        return None
    else:
        raise RuntimeError(f"Command failed: {command} {result.stderr.decode('utf-8')}")


def check_helm(registry: Optional[str]):
    if HELM_CMD is None:
        typer.echo("This command requires helm, helm not found")
        raise typer.Exit(1)
    elif registry is None and K8S_HELM_REGISTRY is None:
        typer.echo("Please set K8S_HELM_REGISTRY or pass --helm-registry")
        raise typer.Exit(1)


def check_tools():

    global K8S_HELM_REGISTRY, DOCKER_CMD, HELM_CMD

    K8S_HELM_REGISTRY = os.environ.get("K8S_HELM_REGISTRY", None)

    DOCKER_CMD = run_command("which podman", error_OK=True)
    if DOCKER_CMD is None:
        DOCKER_CMD = run_command("which docker", error_OK=True)

    HELM_CMD = run_command("which helm", error_OK=True)

    log.warn("DOCKER_CMD=%s", DOCKER_CMD)
    log.warn("HELM_CMD=%s", HELM_CMD)
