import typer

import epics_containers_cli.globals as glob_vars
import epics_containers_cli.shell as shell
from epics_containers_cli.k8s.kubectl import fmt_deploys, fmt_pods

cluster = typer.Typer()


class K8sCommands:
    def __init__(self, ctx: glob_vars.Context):
        self.namespace = ctx.namespace

    def resources(self):
        typer.echo("\nDeployments")
        typer.echo(
            shell.run_command(
                f"kubectl get -n {self.namespace} deployment -l beamline={self.namespace} -o {fmt_deploys}"
            )
        )
        typer.echo("\nPods")
        typer.echo(
            shell.run_command(
                f"kubectl get -n {self.namespace} pod -l beamline={self.namespace} -o {fmt_pods}"
            )
        )
        typer.echo("\nconfigMaps")
        typer.echo(
            shell.run_command(
                f"kubectl get -n {self.namespace} configmap -l beamline={self.namespace}"
            )
        )
        typer.echo("\nPersistent Volume Claims")
        typer.echo(
            shell.run_command(
                f"kubectl get -n {self.namespace} pvc -l beamline={self.namespace}"
            )
        )

    def monitor(self):
        """Monitor the status of IOCs in a domain"""
        typer.echo("Not yet implemented - will be a rich text resizable terminal UI")

        # TODO
