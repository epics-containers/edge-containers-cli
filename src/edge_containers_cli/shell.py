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
        self.dry_run = False

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
        self,
        command: str,
        error_OK=False,
        show=False,
        skip_on_dryrun=False,
    ) -> str:
        """
        Run a command and return the output

        args:
            command: the command to run
            error_OK: if True then do not raise an exception on failure
            show: print the command output to the console
        """
        if self.dry_run:
            self.echo_command(f"(skipped) {command}" if skip_on_dryrun else command)
        elif self.verbose:
            self.echo_command(command)

        if not (self.dry_run and skip_on_dryrun):
            p_result = subprocess.run(command, capture_output=True, shell=True)
            log.debug(f"running: {command}")

            output = p_result.stdout.decode()
            error_out = p_result.stderr.decode()
            result = output + error_out

            if p_result.returncode != 0 and not error_OK:
                if self.verbose:
                    self.echo_error("\nCommand Failed:")
                    self.echo_command(command)
                raise ShellError(error_out)

            if show:
                self.echo_output(output)
                self.echo_error(error_out)

            log.debug(f"returning: {result}")
        else:
            log.debug(f"Dry run - skipping: {command}")
            result = ""
        return result

    def run_interactive(
        self,
        command: str,
        error_OK=False,
        skip_on_dryrun=False,
    ) -> bool:
        """
        Run a command and allow stdin and stdout, returns True on success

        args:
            command: the command to run
            error_OK: if True then do not raise an exception on failure
        """
        if self.dry_run:
            self.echo_command(f"(skipped) {command}" if skip_on_dryrun else command)
        elif self.verbose:
            self.echo_command(command)

        if not (self.dry_run and skip_on_dryrun):
            p_result = subprocess.run(command, capture_output=False, shell=True)
            log.debug(f"running: {command}")

            if p_result.returncode != 0 and not error_OK:
                if self.verbose:
                    self.echo_error("\nCommand Failed:")
                    self.echo_command(command)
                raise ShellError(f"Command:{command} failed")

            result = p_result.returncode == 0
            log.debug(f"returning: {result}")
        else:
            log.info(f"Dry run - skipping: {command}")
            result = True

        return result


shell = ECShell()


def init_shell(verbose: bool, dry_run: bool) -> None:
    shell.verbose = verbose
    shell.dry_run = dry_run
