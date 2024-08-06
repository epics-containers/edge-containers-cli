"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""
from edge_containers_cli.cmds.commands import Commands, ServicesDataFrame, CommandError
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.shell import shell, ShellError
from edge_containers_cli.logging import log
from edge_containers_cli.globals import TIME_FORMAT
import polars
from datetime import datetime
from ruamel.yaml import YAML


def extract_project_app(target:str)-> tuple[str, str]:
    project, app = target.split("/")
    return project, app

class ArgoCommands(Commands):
    """
    A class for implementing the Kubernetes based commands
    """

    def __init__(
        self,
        ctx: ECContext,
    ):
        super().__init__(ctx)

    def logs(self, service_name, prev):
        self._logs(service_name, prev)

    def ps(self, running_only):
        self._ps(running_only)

    def restart(self, service_name):
        self._check_service(service_name)
        project, app = extract_project_app(self.target)
        cmd = (
            f"argocd app delete-resource {project}/{service_name} "
            f"--kind StatefulSet"
            )
        shell.run_command(cmd, skip_on_dryrun=True)

    def start(self, service_name):
        self._check_service(service_name)
        cmd = (
            f"argocd app set {self.target} "
            f"-p services.{service_name}.enabled=true"
            )
        shell.run_command(cmd, skip_on_dryrun=True)

    def stop(self, service_name):
        self._check_service(service_name)
        cmd = (
            f"argocd app set {self.target} "
            f"-p services.{service_name}.enabled=false"
            )
        shell.run_command(cmd, skip_on_dryrun=True)


    def _get_logs(self, service_name, prev) -> str:
        project, app = extract_project_app(self.target)
        self._check_service(service_name)
        previous = "-p" if prev else ""

        logs = shell.run_command(
                f"argocd app logs {project}/{service_name} {previous}",
                error_OK=True,
            )
        return logs

    def _get_services(self, running_only) -> ServicesDataFrame:

        project, app = extract_project_app(self.target)
        app_resp = shell.run_command(
            f"argocd app list -l \"edge-service=True\" --project {project} -o yaml",
        )
        app_dicts = YAML(typ="safe").load(app_resp)

        my_data = {
            "name": [],
            "version": [],
            "ready": [],
            "deployed": [],
              }
        for app in app_dicts:
            resources_dict = app["status"]["resources"]

            for i, resource in enumerate(resources_dict):
                if resource["kind"] == "StatefulSet":
                    name = app["metadata"]["name"]
                    time_stamp = datetime.strptime(app["metadata"]["creationTimestamp"], "%Y-%m-%dT%H:%M:%SZ")

                    # check if replicas ready
                    mani_resp = shell.run_command(
                    f"argocd app manifests {project}/{name} --source live",
                    )
                    for resource_manifest in mani_resp.split("---")[1:]:
                        manifest = YAML(typ="safe").load(resource_manifest)
                        try:
                            if manifest["metadata"]["name"] == name:
                                is_ready = bool(manifest["status"]["readyReplicas"])
                        except (KeyError, TypeError):  # Not ready if doesnt exist
                                is_ready = False

                    # Fill app data
                    my_data["name"].append(name)
                    my_data["version"].append(app["spec"]["source"]["targetRevision"])
                    my_data["ready"].append(is_ready)
                    my_data["deployed"].append(datetime.strftime(time_stamp, TIME_FORMAT))                 

        services_df = polars.from_dict(my_data)

        if running_only:
            services_df = services_df.filter(polars.col("ready").eq(True))
            log.debug(services_df)
        return ServicesDataFrame(services_df)
    
    def _check_service(self, service_name: str):
        """
        validate that there is a pod with the given service_name
        """
        services_list = self._get_services(running_only=False)["name"]
        if service_name in services_list:
            pass
        else:
            raise CommandError(f"Service '{service_name}' not found in {self.target}")

    def _validate_target(self):
        """
        Verify we have a good namespace that exists in the cluster
        """
        cmd = f"argocd app get {self._target}"
        try:
            shell.run_command(cmd, error_OK=False)
        except ShellError as e:
            if "code = Unauthenticated" in str(e):
                raise CommandError("Not authenticated to argocd server")
            elif "code = PermissionDenied" in str(e):
                raise CommandError(f"Target '{self._target}' not found")
            else:
                raise CommandError(str(e))

    def _running_services(self):
        return self._get_services(running_only=True)["name"]

    def _all_services(self):
        return self._get_services(running_only=False)["name"]