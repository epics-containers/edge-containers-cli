import typer

from epics_containers_cli.globals import Context
from epics_containers_cli.k8s.kubectl import fmt_deploys, fmt_pods
from epics_containers_cli.shell import run_command

cluster = typer.Typer()


class K8sCommands:
    def __init__(self, ctx: Context):
        self.namespace = ctx.namespace

    def resources(self):
        typer.echo("\nDeployments")
        typer.echo(
            run_command(
                f"kubectl get -n {self.namespace} deployment -l beamline={self.namespace} -o {fmt_deploys}"
            )
        )
        typer.echo("\nPods")
        typer.echo(
            run_command(
                f"kubectl get -n {self.namespace} pod -l beamline={self.namespace} -o {fmt_pods}"
            )
        )
        typer.echo("\nconfigMaps")
        typer.echo(
            run_command(
                f"kubectl get -n {self.namespace} configmap -l beamline={self.namespace}"
            )
        )
        typer.echo("\nPersistent Volume Claims")
        typer.echo(
            run_command(
                f"kubectl get -n {self.namespace} pvc -l beamline={self.namespace}"
            )
        )

    def monitor(self):
        """Monitor the status of IOCs in a domain"""
        typer.echo("Not yet implemented - will be a rich text resizable terminal UI")

        # TODO
