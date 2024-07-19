"""
functions for executing commands and querying environment in the linux shell
"""

import subprocess

from rich.console import Console
from rich.style import Style

from .logging import log


class ShellError(Exception):
    pass


class ECShell:
    def __init__(self) -> None:
        self.console = Console(highlight=False, soft_wrap=True)
        self.verbose = False

    def set_verbose(self, verbose: bool):
        self.verbose = verbose

    def echo_command(self, command: str):
        """
        print a command to the console
        """
        self.console.print(command, style=Style(color="pale_turquoise4"))

    def echo_error(self, error: str):
        """
        print an error to the console
        """
        self.console.print(error, style=Style(color="red", bold=True))

    def echo_output(self, output: str):
        """
        print an output to the console
        """
        self.console.print(output, style=Style(color="deep_sky_blue3", bold=True))

    def run_command(
        self, command: str, interactive=True, error_OK=False, show=False
    ) -> str | bool:
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
        if self.verbose:
            self.echo_command(command)

        p_result = subprocess.run(command, capture_output=not interactive, shell=True)

        if interactive:
            output = error_out = ""
        else:
            output = p_result.stdout.decode()
            error_out = p_result.stderr.decode()

        if interactive:
            result: str | bool = p_result.returncode == 0
        else:
            result = output + error_out

        if p_result.returncode != 0 and not error_OK:
            self.echo_error("\nCommand Failed:")
            if self.verbose:
                self.echo_command(command)
            self.echo_output(output)
            self.echo_error(error_out)
            raise ShellError(f"Command:{command} failed")

        if show:
            self.echo_output(output)
            self.echo_error(error_out)

        log.debug(f"returning: {result}")

        return result


shell = ECShell()


def init_shell(verbose: bool) -> None:
    shell.set_verbose(verbose)
