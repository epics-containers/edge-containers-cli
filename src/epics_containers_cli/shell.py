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

console = Console(highlight=False, soft_wrap=True)


def echo_command(command: str):
    """
    print a command to the console
    """
    console.print(command, style=Style(color="pale_turquoise4"))


def echo_error(error: str):
    """
    print an error to the console
    """
    console.print(error, style=Style(color="red", bold=True))


def echo_output(output: str):
    """
    print an output to the console
    """
    console.print(output, style=Style(color="deep_sky_blue3", bold=True))


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
    if glob_vars.EC_VERBOSE:
        echo_command(command)

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
        echo_error("\nCommand Failed:")
        if not glob_vars.EC_VERBOSE:
            echo_command(command)
        echo_output(output)
        echo_error(error_out)
        raise typer.Exit(1)

    if show:
        echo_output(output)
        echo_error(error_out)

    log.debug(f"returning: {result}")

    return result


def check_beamline_repo(repo: str):
    if repo == "":
        typer.echo("Please set EC_DOMAIN_REPO or pass --repo")
        raise typer.Exit(1)
