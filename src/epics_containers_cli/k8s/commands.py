import typer

from ..globals import Context
from ..shell import run_command
from .kubectl import fmt_deploys, fmt_pods

cluster = typer.Typer()


class K8sCommands:
    def __init__(self, ctx: Context):
        self.domain = ctx.domain

    def resources(self):
        typer.echo("\nDeployments")
        typer.echo(
            run_command(
                f"kubectl get -n {self.domain} deployment -l beamline={self.domain} -o {fmt_deploys}"
            )
        )
        typer.echo("\nPods")
        typer.echo(
            run_command(
                f"kubectl get -n {self.domain} pod -l beamline={self.domain} -o {fmt_pods}"
            )
        )
        typer.echo("\nconfigMaps")
        typer.echo(
            run_command(
                f"kubectl get -n {self.domain} configmap -l beamline={self.domain}"
            )
        )
        typer.echo("\nPersistent Volume Claims")
        typer.echo(
            run_command(f"kubectl get -n {self.domain} pvc -l beamline={self.domain}")
        )

    def monitor():
        """Monitor the status of IOCs in a domain"""
        typer.echo("Not yet implemented - will be a rich text resizable terminal UI")

        # TODO
