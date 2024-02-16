"""
implements commands for deploying and managing service instances in the k8s cluster.

Relies on the Helm class for deployment aspects.
"""

import webbrowser
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

import edge_containers_cli.globals as globals
import edge_containers_cli.shell as shell
from edge_containers_cli.cmds.helm import Helm
from edge_containers_cli.cmds.kubectl import json_service_info, json_service_types
from edge_containers_cli.logging import log


def check_service(service_name: str, namespace: str) -> str:
    """
    validate that there is a pod with the given service_name and
    determine if it is managed by a statefulset or deployment
    """
    cmd = f"kubectl get {{t}} -o name -n {namespace} {service_name} --ignore-not-found"
    for t in ["statefulset", "deployment"]:
        result = shell.run_command(cmd.format(t=t), interactive=False, error_OK=True)
        if result:
            break
    else:
        log.error(f"{service_name} does not exist in domain {namespace}")
        raise typer.Exit(1)

    # return statefulset/name or deployment/name
    log.debug(f"fullname = {result}")
    return str(result).strip()


def check_namespace(namespace: Optional[str]):
    """
    Verify we have a good namespace that exists in the cluster
    """
    if not namespace:
        log.error("Please set EC_K8S_NAMESPACE or pass --namespace")
        raise typer.Exit(1)

    cmd = f"kubectl get namespace {namespace} -o name"
    result = shell.run_command(cmd, interactive=False, error_OK=True)
    if "NotFound" in str(result):
        log.error(
            f"namespace {namespace} not found - please check "
            f"~/.kube/config or change EC_K8S_NAMESPACE"
        )
        raise typer.Exit(1)

    log.info("domain = %s", namespace)


class K8sCommands:
    """
    A class for implementing the Kubernetes based commands
    """

    def __init__(
        self,
        ctx: Optional[globals.Context],
        service_name: str = "",
        check: bool = True,
    ):
        self.namespace: str = ""
        self.beamline_repo: str = ""
        self.service_type: str = ""
        # TODO isnt ctx always set??
        if ctx is not None:
            namespace = ctx.namespace
            check_namespace(namespace)
            if service_name != "" and check:
                self.fullname = check_service(service_name, namespace)
            self.namespace = namespace
            self.beamline_repo = ctx.beamline_repo
        self.service_name: str = service_name

    def attach(self):
        shell.run_command(
            f"kubectl -it -n {self.namespace} attach {self.fullname}",
            interactive=True,
        )

    def delete(self):
        if not typer.confirm(
            f"This will remove all versions of {self.service_name} "
            "from the cluster. Are you sure ?"
        ):
            raise typer.Abort()

        shell.run_command(f"helm delete -n {self.namespace} {self.service_name}")

    def template(self, svc_instance: Path, args: str):
        datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")

        service_name = svc_instance.name.lower()

        chart = Helm(
            self.namespace,
            service_name,
            args=args,
            template=True,
            repo=self.beamline_repo,
        )
        chart.deploy_local(svc_instance)

    def deploy_local(self, svc_instance: Path, yes: bool, args: str):
        service_name = svc_instance.name.lower()

        chart = Helm(self.namespace, service_name, args=args)
        chart.deploy_local(svc_instance, yes)

    def deploy(self, service_name: str, version: str, args: str):
        chart = Helm(
            self.namespace,
            service_name,
            args,
            version,
            repo=self.beamline_repo,
        )
        chart.deploy()

    def exec(self):
        shell.run_command(
            f"kubectl -it -n {self.namespace} exec {self.fullname} -- bash"
        )

    def log_history(self):
        if not globals.EC_LOG_URL:
            log.error("EC_LOG_URL environment not set")
            raise typer.Exit(1)

        url = globals.EC_LOG_URL.format(service_name=self.service_name)
        webbrowser.open(url)

    def logs(self, prev: bool, follow: bool):
        previous = "-p" if prev else ""
        fol = "-f" if follow else ""

        shell.run_command(
            f"kubectl -n {self.namespace} logs {self.fullname} {previous} {fol}"
        )

    def restart(self):
        pod_name = shell.run_command(
            f"kubectl get -n {self.namespace} pod -l app={self.service_name} -o name",
            interactive=False,
        )
        shell.run_command(f"kubectl delete -n {self.namespace} {pod_name}")

    def start(self):
        shell.run_command(
            f"kubectl scale -n {self.namespace} {self.fullname} --replicas=1"
        )

    def stop(self):
        """Stop an IOC"""
        shell.run_command(
            f"kubectl scale -n {self.namespace} {self.fullname} --replicas=0 "
        )

    def ps(self, all: bool, wide: bool):
        """List all IOCs and Services in the current namespace"""

        helm_json = shell.run_command(
            f"helm list -n {self.namespace} -o json", interactive=False
        )
        df = pd.read_json(StringIO(str(helm_json)))
        log.debug(df)

        if not all:
            # only show running services - get the pods list and merge with helm list
            services_csv = shell.run_command(
                f"kubectl get pods -n {self.namespace} {json_service_info}",
                interactive=False,
            )
            pods_df = pd.read_csv(  # type: ignore
                StringIO(str(services_csv)),
                names=json_service_types.keys(),  # type: ignore
                dtype=json_service_types,  # type: ignore
            )
            log.debug(pods_df)

            df = pd.merge(pods_df, df, left_on="name", right_on="name")

        df.drop(columns=["revision", "updated", "status", "chart"], inplace=True)

        print(df.to_string(index=False))
