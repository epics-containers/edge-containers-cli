"""
functions for executing commands and querying environment in the linux shell
"""

import subprocess
from typing import Union

import typer
from rich.console import Console
from rich.style import Style

import epics_containers_cli.globals as glob_vars

from .logging import log


def run_command(command: str, interactive=True, error_OK=False) -> Union[str, bool]:
    """
    Run a command and return the output

    if interactive is true then allow stdin and stdout, return the return code,
    otherwise return True for success and False for failure
    """
    if glob_vars.EC_VERBOSE:
        Console(highlight=False).print(
            command, style=Style(color="pale_turquoise4", bold=True)
        )

    p_result = subprocess.run(command, capture_output=not interactive, shell=True)

    output = "" if interactive else p_result.stdout.decode() + p_result.stderr.decode()

    if p_result.returncode != 0 and not error_OK:
        raise RuntimeError(f"Command Failed:\n{command}\n{output}\n")

    if interactive:
        result: Union[str, bool] = p_result.returncode == 0
    else:
        result = p_result.stdout.decode() + p_result.stderr.decode()
    log.debug(f"returning: {result}")
    return result


def check_beamline_repo(repo: str):
    if repo == "":
        typer.echo("Please set EC_DOMAIN_REPO or pass --repo")
        raise typer.Exit(1)
