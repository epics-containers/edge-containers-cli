"""
functions for executing commands and querying environment in the linux shell
"""

import os
import subprocess
from typing import Union

import typer

from .logging import log

EC_GIT_ORG = os.environ.get("EC_GIT_ORG", "")
EC_DOMAIN_REPO = os.environ.get("EC_DOMAIN_REPO", "")
EC_REGISTRY_MAPPING = os.environ.get(
    "EC_REGISTRY_MAPPING",
    "github.com=ghcr.io gitlab.diamond.ac.uk=gcr.io/diamond-privreg/controls/ioc",
)
EC_K8S_NAMESPACE = os.environ.get("EC_K8S_NAMESPACE", "")
EC_LOG_URL = os.environ.get("EC_LOG_URL", None)
EC_CONTAINER_CLI = os.environ.get("EC_CONTAINER_CLI")  # default to auto choice
# local deploy means we use docker standalone on the local machine for deployment
# users of this feature could use portainer or other management tools to
# track and manage the IOC local deployments
EC_LOCAL_DEPLOY = EC_K8S_NAMESPACE == ""


def run_command(command: str, interactive=True, error_OK=False) -> Union[str, bool]:
    """
    Run a command and return the output

    if interactive is true then allow stdin and stdout, return the return code,
    otherwise return True for success and False for failure
    """
    log.debug(
        f"running command:\n   {command}\n   "
        f"(interactive={interactive}, error_OK={error_OK})\n"
    )

    p_result = subprocess.run(command, capture_output=not interactive, shell=True)

    output = "" if interactive else p_result.stdout.decode() + p_result.stderr.decode()

    if p_result.returncode != 0 and not error_OK:
        log.error(f"Command Failed:\n{command}\n{output}\n")
        raise typer.Exit(1)

    if interactive:
        result: Union[str, bool] = p_result.returncode == 0
    else:
        result = p_result.stdout.decode() + p_result.stderr.decode()
    log.debug(f"returning: {result}")
    return result
