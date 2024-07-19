"""
implements commands for deploying and managing service instances in the k8s cluster.

Relies on the Helm class for deployment aspects.
"""

from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

import polars

from edge_containers_cli.cmds.commands import CommandError, Commands
from edge_containers_cli.cmds.helm import Helm
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.logging import log
from edge_containers_cli.shell import shell


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
        raise CommandError(f"{service_name} does not exist in domain {namespace}")

    # return statefulset/name or deployment/name
    log.debug(f"fullname = {result}")
    return str(result).strip()


class K8sCommands(Commands):
    """
    A class for implementing the Kubernetes based commands
    """

    def __init__(
        self,
        ctx: ECContext,
    ):
        super().__init__(ctx)

        # Check backend is available?

    def attach(self, service_name):
        fullname = check_service(service_name, self.namespace)
        shell.run_command(
            f"kubectl -it -n {self.namespace} attach {fullname}",
            interactive=True,
        )

    def delete(self, service_name):
        check_service(service_name, self.namespace)
        shell.run_command(f"helm delete -n {self.namespace} {service_name}")

    def deploy(self, service_name: str, version: str, args: str):
        chart = Helm(
            self.namespace,
            service_name,
            args,
            version,
            repo=self.repo,
        )
        chart.deploy()

    def deploy_local(self, svc_instance: Path, args: str):
        service_name = svc_instance.name.lower()
        chart = Helm(self.namespace, service_name, args=args)
        chart.deploy_local(svc_instance)

    def exec(self, service_name):
        fullname = check_service(service_name, self.namespace)
        shell.run_command(f"kubectl -it -n {self.namespace} exec {fullname} -- bash")

    def logs(
        self, service_name: str, prev: bool, follow: bool, stdout: bool = False
    ) -> Optional[str | bool]:
        fullname = check_service(service_name, self.namespace)
        previous = "-p" if prev else ""
        fol = "-f" if follow else ""

        if stdout:
            a = shell.run_command(
                f"kubectl -n {self.namespace} logs {fullname} {previous} {fol}",
                interactive=False,
                show=False,
                error_OK=True,
            )
            return a
        else:
            shell.run_command(
                f"kubectl -n {self.namespace} logs {fullname} {previous} {fol}",
            )
            return None

    def ps(self, running_only: bool, wide: bool):
        """List all IOCs and Services in the current namespace"""
        self._ps(running_only, wide)

    def restart(self, service_name):
        check_service(service_name, self.namespace)
        pod_name = shell.run_command(
            f"kubectl get -n {self.namespace} pod -l app={service_name} -o name",
            interactive=False,
        )
        shell.run_command(f"kubectl delete -n {self.namespace} {pod_name}")

    def start(self, service_name):
        fullname = check_service(service_name, self.namespace)
        shell.run_command(f"kubectl scale -n {self.namespace} {fullname} --replicas=1")

    def stop(self, service_name):
        fullname = check_service(service_name, self.namespace)
        """Stop an IOC"""
        shell.run_command(f"kubectl scale -n {self.namespace} {fullname} --replicas=0 ")

    def template(self, svc_instance: Path, args: str):
        datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")

        service_name = svc_instance.name.lower()

        chart = Helm(
            self.namespace,
            service_name,
            args=args,
            template=True,
            repo=self.repo,
        )
        chart.deploy_local(svc_instance)

    def _get_services(self, running_only: bool) -> polars.DataFrame:
        services_df = polars.DataFrame()

        # Gives all services (running & not running) and their image
        for resource in ["deployment", "statefulset"]:
            kubectl_res = shell.run_command(
                f"kubectl get {resource} -n {self.namespace} {jsonpath_deploy_info}",
                interactive=False,
            )
            if kubectl_res:
                res_df = polars.read_csv(
                    StringIO(str(kubectl_res)),
                    separator=",",
                    has_header=False,
                    new_columns=["name", "image"],
                )
                log.debug(res_df)
                services_df = polars.concat([services_df, res_df], how="diagonal")
        if services_df.is_empty():
            print("No deployed services found")
            raise CommandError("No deployed services found")

        # Gives the status, restarts for running services
        kubectl_gtpo = shell.run_command(
            f"kubectl get pods -n {self.namespace} {jsonpath_pod_info}",
            interactive=False,
        )
        if kubectl_gtpo:
            gtpo_df = polars.read_csv(
                StringIO(str(kubectl_gtpo)),
                separator=",",
                has_header=False,
                new_columns=["name", "running", "restarts"],
            )
            services_df = services_df.join(
                gtpo_df, on="name", how="left", coalesce=True
            )
            services_df = services_df.with_columns(
                polars.col("running").replace({"Running": True}, default=False),
                polars.col("restarts").fill_null(0),
            )
        elif not running_only:
            services_df = services_df.with_columns(
                running=polars.lit(False), restarts=polars.lit(0)
            )
        else:
            raise CommandError("No running services found")

        # Adds the version, deployment time for all services
        helm_out = shell.run_command(
            f"helm list -n {self.namespace} -o json", interactive=False
        )
        helm_df = polars.read_json(StringIO(str(helm_out)))
        helm_df = helm_df.rename({"app_version": "version", "updated": "deployed"})
        helm_df = helm_df.with_columns(polars.col("deployed").str.slice(0, 19))
        services_df = services_df.join(helm_df, on="name", how="left", coalesce=True)
        log.debug(services_df)

        # Arrange columns
        services_df = services_df.select(
            ["name", "version", "running", "restarts", "deployed", "image"]
        )
        if running_only:
            services_df = services_df.filter(polars.col("running").eq(True))
            log.debug(services_df)
        return services_df

    def _validate_namespace(self):
        """
        Verify we have a good namespace that exists in the cluster
        """
        cmd = f"kubectl get namespace {self._namespace} -o name"
        result = shell.run_command(cmd, interactive=False, error_OK=True)
        if "NotFound" in str(result):
            raise CommandError(f"Namespace '{self._namespace}' not found")
        log.info("domain = %s", self._namespace)

    def _all_services(self) -> list[str]:
        columns = "-o custom-columns=NAME:metadata.name"
        namespace = f"-n {self.namespace}"
        labels = "-l is_ioc==true"
        command = f"kubectl {namespace} {labels} get statefulset {columns}"
        all_list = str(shell.run_command(command, interactive=False)).split()[1:]

        return all_list

    def _running_services(self) -> list[str]:
        all = self._all_services()

        columns = "-o custom-columns=NAME:metadata.name"
        namespace = f"-n {self.namespace}"
        labels = "-l is_ioc==true"
        selector = "--field-selector=status.phase==Running"
        command = f"kubectl {namespace} {labels} get pod {selector} {columns}"
        running_list = str(shell.run_command(command, interactive=False))
        for svc in all:
            if svc in running_list:
                pass
            else:
                all.remove(svc)
        return all


jsonpath_pod_info = (
    "-o jsonpath='"
    r'{range .items[*]}{..labels.app}{..labels.app\.kubernetes\.io/instance}{","}{.status.phase}'
    r'{","}{..containerStatuses[0].restartCount}'
    r'{"\n"}{end}'
    "'"
)

jsonpath_deploy_info = (
    "-o jsonpath='"
    r'{range .items[*]}{.metadata.name}{","}'
    r"{range .spec.template.spec.containers[*]}{.image}"
    r'{"\n"}{end}{end}'
    "'"
)
