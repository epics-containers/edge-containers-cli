"""
implements commands for deploying and managing ioc instances in the k8s cluster.

Relies on the Helm class for deployment aspects.
"""
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.globals import Context
from epics_containers_cli.ioc.helm import Helm
from epics_containers_cli.k8s.kubectl import fmt_deploys, fmt_pods, fmt_pods_wide
from epics_containers_cli.logging import log
from epics_containers_cli.shell import run_command


def check_ioc(ioc_name: str, domain: str):
    cmd = f"kubectl get -n {domain} deploy/{ioc_name}"
    if not run_command(cmd, interactive=False, error_OK=True):
        log.error(f"ioc {ioc_name} does not exist in domain {domain}")
        raise typer.Exit(1)


def check_namespace(namespace: Optional[str]):
    """
    Verify we have a good namespace that exists in the cluster
    """
    if not namespace:
        log.error("Please set EC_K8S_NAMESPACE or pass --namespace")
        raise typer.Exit(1)

    cmd = f"kubectl get namespace {namespace} -o name"
    result = run_command(cmd, interactive=False, error_OK=True)
    if "NotFound" in str(result):
        log.error(
            f"namespace {namespace} not found - please check "
            f"~/.kube/config or change EC_K8S_NAMESPACE"
        )
        raise typer.Exit(1)

    log.info("domain = %s", namespace)


class IocK8sCommands:
    """
    A class for implementing the ioc command namespace
    """

    def __init__(self, ctx: Optional[Context], ioc_name: str = ""):
        self.namespace: str = ""
        self.beamline_repo: str = ""
        if ctx is not None:
            namespace = ctx.namespace
            check_namespace(namespace)
            if ioc_name != "":
                check_ioc(ioc_name, namespace)
            self.namespace = namespace
            self.beamline_repo = ctx.beamline_repo
        self.ioc_name: str = ioc_name

    def attach(self):
        run_command(
            f"kubectl -it -n {self.namespace} attach deploy/{self.ioc_name}",
            interactive=True,
        )

    def delete(self):
        if not typer.confirm(
            f"This will remove all versions of {self.ioc_name} "
            "from the cluster. Are you sure ?"
        ):
            raise typer.Abort()

        run_command(f"helm delete -n {self.namespace} {self.ioc_name}")

    def template(self, ioc_instance: Path, args: str):
        datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")

        ioc_name = ioc_instance.name.lower()

        chart = Helm(
            self.namespace, ioc_name, args=args, template=True, repo=self.beamline_repo
        )
        chart.deploy_local(ioc_instance)

    def deploy_local(self, ioc_instance: Path, yes: bool, args: str):
        ioc_name = ioc_instance.name.lower()

        chart = Helm(self.namespace, ioc_name, args=args)
        chart.deploy_local(ioc_instance, yes)

    def deploy(self, ioc_name: str, version: str, args: str):
        chart = Helm(self.namespace, ioc_name, args, version, repo=self.beamline_repo)
        chart.deploy()

    def instances(self):
        chart = Helm(self.namespace, self.ioc_name, repo=self.beamline_repo)
        chart.versions()

    def exec(self):
        run_command(
            f"kubectl -it -n {self.namespace} exec deploy/{self.ioc_name} -- bash"
        )

    def log_history(self):
        if not glob_vars.EC_LOG_URL:
            log.error("K8S_LOG_URL environment not set")
            raise typer.Exit(1)

        url = glob_vars.EC_LOG_URL.format(ioc_name=self.ioc_name)
        webbrowser.open(url)

    def logs(self, prev: bool, follow: bool):
        previous = "-p" if prev else ""
        fol = "-f" if follow else ""

        run_command(
            f"kubectl -n {self.namespace} logs deploy/{self.ioc_name} {previous} {fol}"
        )

    def restart(self):
        pod_name = run_command(
            f"kubectl get -n {self.namespace} pod -l app={self.ioc_name} -o name",
            interactive=False,
        )
        run_command(f"kubectl delete -n {self.namespace} {pod_name}")

    def start(self):
        run_command(
            f"kubectl scale -n {self.namespace} deploy/{self.ioc_name} --replicas=1"
        )

    def stop(self):
        """Stop an IOC"""
        run_command(
            f"kubectl scale -n {self.namespace} deploy/{self.ioc_name} --replicas=0 "
        )

    def ps(self, all: bool, wide: bool):
        """List all IOCs in the current namespace"""

        if all:
            run_command(
                f"kubectl -n {self.namespace} get deploy -l is_ioc==True -o {fmt_deploys}"
            )
        else:
            format = fmt_pods_wide if wide else fmt_pods
            run_command(
                f"kubectl -n {self.namespace} get pod -l is_ioc==True -o {format}"
            )
