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


def run_command(
    command: str, interactive=True, error_OK=False, show=False
) -> Union[str, bool]:
    """
    Run a command and return the output

    if interactive is true then allow stdin and stdout, return the return code,
    otherwise return True for success and False for failure

    args:

        command: the command to run
        interactive: if True then allow stdin and stdout
        error_OK: if True then do not raise an exception on failure
        show: print the command output to the console
    """
    console = Console(highlight=False, soft_wrap=True)

    if glob_vars.EC_VERBOSE:
        console.print(command, style=Style(color="pale_turquoise4"))

    p_result = subprocess.run(command, capture_output=not interactive, shell=True)

    if interactive:
        output = error_out = ""
    else:
        output = p_result.stdout.decode()
        error_out = p_result.stderr.decode()

    if interactive:
        result: Union[str, bool] = p_result.returncode == 0
    else:
        result = output + error_out

    if p_result.returncode != 0 and not error_OK:
        console.print("\nCommand Failed:", style=Style(color="red", bold=True))
        if not glob_vars.EC_VERBOSE:
            console.print(f"{command}", style=Style(color="pale_turquoise4"))
        console.print(output, style=Style(color="deep_sky_blue3", bold=True))
        console.print(error_out, style=Style(color="red", bold=True))
        raise typer.Exit(1)

    if show:
        console.print(output, style=Style(color="deep_sky_blue3", bold=True))
        console.print(error_out, style=Style(color="red", bold=True))

    log.debug(f"returning: {result}")

    return result


def check_beamline_repo(repo: str):
    if repo == "":
        typer.echo("Please set EC_DOMAIN_REPO or pass --repo")
        raise typer.Exit(1)
