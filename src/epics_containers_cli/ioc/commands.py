import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from ..globals import Context
from ..shell import EC_LOG_URL, check_domain, check_ioc, run_command
from .helm import Helm


class IocCommands:
    """
    A class for implementing the ioc command namespace
    """

    def __init__(self, ctx: Context, ioc_name: Optional[str]):
        if ctx is None:
            domain = None
        else:
            domain = ctx.domain
            check_domain(domain)
            if ioc_name is not None:
                check_ioc(ioc_name, domain)
        self.domain = domain
        self.ioc_name = ioc_name
        self.beamline_repo = ctx.beamline_repo

    def attach(self):
        run_command(
            f"kubectl -it -n {self.domain} attach  deploy/{self.ioc_name}",
            interactive=True,
        )

    def delete(self):
        if not typer.confirm(
            f"This will remove all versions of {self.ioc_name} "
            "from the cluster. Are you sure ?"
        ):
            raise typer.Abort()

        run_command(f"helm delete -n {self.domain} {self.ioc_name}")

    def template(self, ioc_instance: Path, args: str):
        datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")

        ioc_name = ioc_instance.name.lower()

        chart = Helm(
            self.domain, ioc_name, args=args, template=True, repo=self.beamline_repo
        )
        chart.deploy_local(ioc_instance)

    def deploy_local(self, ioc_instance: Path, yes: bool, args: str):
        ioc_name = ioc_instance.name.lower()

        chart = Helm(self.domain, ioc_name, args=args)
        chart.deploy_local(ioc_instance, yes)

    def deploy(self, ioc_name: str, version: str, args: str):
        chart = Helm(self.domain, ioc_name, args, version, repo=self.beamline_repo)
        chart.deploy()

    def instances(self):
        chart = Helm(self.domain, self.ioc_name, repo=self.beamline_repo)
        chart.versions()

    def exec(self, ioc_name: str):
        run_command(f"kubectl -it -n {self.domain} exec  deploy/{ioc_name} -- bash")

    def log_history(self, ioc_name: str):
        if EC_LOG_URL is None:
            typer.echo("K8S_LOG_URL environment not set")
            raise typer.Exit(1)

        url = EC_LOG_URL.format(ioc_name=ioc_name)
        webbrowser.open(url)

    def logs(self, prev: bool, follow: bool):
        previous = "-p" if prev else ""
        fol = "-f" if follow else ""

        run_command(
            f"kubectl -n {self.domain} logs deploy/{self.ioc_name} {previous} {fol}"
        )

    def restart(self):
        pod_name = run_command(
            f"kubectl get -n {self.domain} pod -l app={self.ioc_name} -o name",
            interactive=False,
        )
        run_command(f"kubectl delete -n {self.domain} {pod_name}")

    def stop(self):
        """Stop an IOC"""
        run_command(
            f"kubectl scale -n {self.domain} deploy --replicas=0 {self.ioc_name}"
        )
