"""
implements commands for deploying and managing service instances in the k8s cluster.

Relies on the Helm class for deployment aspects.
"""

import webbrowser
from datetime import datetime
from io import StringIO

import polars
from ruamel.yaml import YAML

from edge_containers_cli.cmds.commands import (
    CommandError,
    Commands,
    ServicesDataFrame,
)
from edge_containers_cli.cmds.helm import Helm
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.globals import TIME_FORMAT
from edge_containers_cli.shell import ShellError, shell


class K8sCommands(Commands):
    """
    A class for implementing the Kubernetes based commands
    """

    params_opt_out = {
        "stop": ["commit"],
        "start": ["commit"],
    }

    def __init__(
        self,
        ctx: ECContext,
    ):
        super().__init__(ctx)

    def attach(self, service_name):
        self._check_service(service_name)
        shell.run_interactive(
            f"kubectl -it -n {self.target} attach statefulset {service_name}",
            skip_on_dryrun=True,
        )

    def delete(self, service_name, commit=False):
        self._check_service(service_name)
        shell.run_command(
            f"helm delete -n {self.target} {service_name}", skip_on_dryrun=True
        )

    def deploy(self, service_name, version, args, confirm_callback=None):
        latest_version = self._get_latest_version(service_name)
        if not version:
            version = latest_version

        chart = Helm(
            self.target,
            service_name,
            args,
            version,
            repo=self.repo,
        )
        chart.deploy(confirm_callback)

    def deploy_local(self, svc_instance, args, confirm_callback=None):
        service_name = svc_instance.name.lower()
        chart = Helm(self.target, service_name, args=args)
        chart.deploy_local(svc_instance, confirm_callback)

    def exec(self, service_name):
        self._check_service(service_name)
        shell.run_interactive(
            f"kubectl -it -n {self.target} exec statefulset/{service_name} -- bash",
            skip_on_dryrun=True,
        )

    def logs(self, service_name, prev):
        self._logs(service_name, prev)

    def log_history(self, service_name):
        self._check_service(service_name)
        url = self.log_url.format(service_name=service_name)
        webbrowser.open(url)

    def ps(self, running_only):
        self._ps(running_only)

    def restart(self, service_name):
        self._check_service(service_name)
        pod_name = shell.run_command(
            f"kubectl get -n {self.target} pod -l app={service_name} -o name",
        )
        shell.run_command(
            f"kubectl delete -n {self.target} {pod_name}", skip_on_dryrun=True
        )

    def start(self, service_name, commit=False):
        self._check_service(service_name)
        shell.run_command(
            f"kubectl scale -n {self.target} statefulset {service_name} --replicas=1",
            skip_on_dryrun=True,
        )

    def stop(self, service_name, commit=False):
        self._check_service(service_name)
        shell.run_command(
            f"kubectl scale -n {self.target} statefulset {service_name} --replicas=0 ",
            skip_on_dryrun=True,
        )

    def template(self, svc_instance, args):
        datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")

        service_name = svc_instance.name.lower()

        chart = Helm(
            "",
            service_name,
            args=args,
            template=True,
        )
        chart.deploy_local(svc_instance)

    def _get_services(self, running_only):
        services_df = polars.DataFrame()

        # Get all statefulset services (running & not running)
        kubectl_res = shell.run_command(
            f'kubectl get statefulset -l "is_ioc==true" -n {self.target} -o yaml',
        )
        sts_dicts = YAML(typ="safe").load(kubectl_res)
        service_data = {
            "name": [],  # type: ignore
            "ready": [],
            "deployed": [],
        }
        if sts_dicts["items"]:
            for sts in sts_dicts["items"]:
                name = sts["metadata"]["name"]
                time_stamp = datetime.strptime(
                    sts["metadata"]["creationTimestamp"], "%Y-%m-%dT%H:%M:%SZ"
                )
                try:
                    is_ready = bool(sts["status"]["readyReplicas"])
                except KeyError:  # Not ready if doesnt exist
                    is_ready = False

                # Fill app data
                service_data["name"].append(name)
                service_data["ready"].append(is_ready)
                service_data["deployed"].append(
                    datetime.strftime(time_stamp, TIME_FORMAT)
                )

        services_df = polars.from_dict(
            service_data,
            schema=polars.Schema(
                {
                    "name": polars.String,
                    "ready": polars.Boolean,
                    "deployed": polars.String,
                }
            ),
        )

        # Adds the version for all services
        helm_out = str(shell.run_command(f"helm list -n {self.target} -o json"))
        if helm_out == "[]\n":
            helm_df = polars.DataFrame(
                schema=polars.Schema({"name": polars.String, "version": polars.String})
            )
        else:
            helm_df = polars.read_json(StringIO(str(helm_out)))
            helm_df = helm_df.rename({"app_version": "version"})

        services_df = services_df.join(
            helm_df.select(["name", "version"]),
            on="name",
            how="left",
            coalesce=True,
        )

        # Arrange columns
        services_df = services_df.select(["name", "version", "ready", "deployed"])
        if running_only:
            services_df = services_df.filter(polars.col("ready").eq(True))
        return ServicesDataFrame(services_df)

    def _get_logs(self, service_name, prev):
        self._check_service(service_name)
        previous = "-p" if prev else ""

        logs = shell.run_command(
            f"kubectl -n {self.target} logs statefulset/{service_name} {previous}",
            error_OK=True,
        )
        return logs

    def _validate_target(self):
        """
        Verify we have a good namespace that exists in the cluster
        """
        cmd = f"kubectl get namespace {self._target}"
        try:
            shell.run_command(cmd, error_OK=False)
        except ShellError as e:
            if "NotFound" in str(e):
                raise CommandError(f"Namespace '{self._target}' not found") from e
            else:
                raise
