"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""

import re
import webbrowser
from datetime import datetime
from pathlib import Path
from time import sleep

import polars
from ruamel.yaml import YAML

from edge_containers_cli import globals
from edge_containers_cli.cmds.commands import (
    CommandError,
    Commands,
    ServicesDataFrame,
    ServicesSchema,
)
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.git import del_key, set_value
from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError, shell
from edge_containers_cli.utils import YamlTypes


def extract_ns_app(target: str) -> tuple[str, str]:
    namespace, app = target.split("/")
    return namespace, app


def get_patches(target) -> dict:
    app_resp = shell.run_command(
        f"argocd app get --show-params {target} -o json",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    try:
        patch_dict = app_dicts["spec"]["source"]["helm"]["parameters"]
    except KeyError:
        patch_dict = {}
    return patch_dict


def do_retry(cmd):
    def _do_retry(*args, **kwargs):
        max_attempts = 5
        attempt = 1
        sleep_time = 1
        while attempt <= max_attempts:
            try:
                cmd(*args, **kwargs)
                return None
            except ShellError:
                if attempt == max_attempts:
                    log.debug(f"Retry failed after {max_attempts} attempts")
                    raise
                else:
                    log.debug(f"Retry attempt {attempt} failed. Retrying...")
                    sleep(sleep_time)
                    attempt += 1

    return _do_retry


@do_retry
def patch_value(target: str, key: str, value: YamlTypes):
    cmd_temp_ = f"argocd app set {target} -p {key}={value}"
    shell.run_command(cmd_temp_, skip_on_dryrun=True)
    # Rely on argocd autosync to get the cluster into the right state


@do_retry
def push_value(target: str, key: str, value: YamlTypes):
    # Get source details
    app_resp = shell.run_command(
        f"argocd app get {target} -o yaml",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    repo_url = app_dicts["spec"]["source"]["repoURL"]
    path = Path(app_dicts["spec"]["source"]["path"])

    set_value(repo_url, path / "values.yaml", key, value)

    # Free a possible patched value & refresh repo
    cmd_unset = f"argocd app unset {target} -p {key}"
    shell.run_command(cmd_unset, skip_on_dryrun=True)
    cmd_refresh = f"argocd app get {target} --refresh"
    shell.run_command(cmd_refresh, skip_on_dryrun=True)
    # Rely on argocd autosync to get the cluster into the right state


@do_retry
def push_remove_key(target: str, key: str):
    # Get source details
    app_resp = shell.run_command(
        f"argocd app get {target} -o yaml",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    repo_url = app_dicts["spec"]["source"]["repoURL"]
    path = Path(app_dicts["spec"]["source"]["path"])

    del_key(repo_url, path / "values.yaml", key)

    # Free a possible patched value, its children & refresh repo
    cmd_unset = f"argocd app unset {target} -p {key}"
    shell.run_command(cmd_unset, skip_on_dryrun=True)
    app_patches = get_patches(target)
    for patch in app_patches:
        if re.match(rf"{key}\..*", patch["name"]):
            cmd_unset_child = f"argocd app unset {target} -p {patch['name']}"
            shell.run_command(cmd_unset_child, skip_on_dryrun=True)
    cmd_refresh = f"argocd app get {target} --refresh"
    shell.run_command(cmd_refresh, skip_on_dryrun=True)
    # Rely on argocd autosync to get the cluster into the right state


def get_services_repo(deployment_repo_url: str) -> str:
    services_repo_url = ""
    return services_repo_url


class ArgoCommands(Commands):
    """
    A class for implementing the Kubernetes based commands
    """

    params_opt_out = {
        "deploy": ["args", "wait"],
    }

    def __init__(
        self,
        ctx: ECContext,
    ):
        super().__init__(ctx)

    def delete(self, service_name: str) -> None:
        self._check_service(service_name)
        push_remove_key(self.target, f"ec_services.{service_name}")

    def deploy(self, service_name, version, args, confirm_callback=None) -> None:
        latest_version = self._get_latest_version(service_name)
        if not version:
            version = latest_version
        if confirm_callback:
            confirm_callback(version)
        deploy_dict: YamlTypes = {"enabled": True, "targetRevision": version}

        push_value(self.target, f"ec_services.{service_name}", deploy_dict)

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
        namespace, app = extract_ns_app(self.target)
        cmd = (
            f"argocd app delete-resource {namespace}/{service_name} --kind StatefulSet"
        )
        shell.run_command(cmd, skip_on_dryrun=True)

    def start(self, service_name, commit=False):
        self._check_service(service_name)
        if commit:
            push_value(self.target, f"ec_services.{service_name}.enabled", True)
        else:
            patch_value(self.target, f"ec_services.{service_name}.enabled", True)

    def stop(self, service_name, commit=False):
        self._check_service(service_name)
        if commit:
            push_value(self.target, f"ec_services.{service_name}.enabled", False)
        else:
            patch_value(self.target, f"ec_services.{service_name}.enabled", False)

    def _get_logs(self, service_name, prev) -> str:
        namespace, app = extract_ns_app(self.target)
        self._check_service(service_name)
        previous = "-p" if prev else ""

        logs = shell.run_command(
            f"argocd app logs {namespace}/{service_name} {previous}",
            error_OK=True,
        )
        return logs

    def _get_services(self, running_only) -> ServicesDataFrame:
        namespace, app = extract_ns_app(self.target)
        service_data = {
            "name": [],  # type: ignore
            "version": [],
            "ready": [],
            "deployed": [],
        }
        app_resp = shell.run_command(
            f'argocd app list -l "ec_service=true" --app-namespace {namespace} -o yaml',
        )
        app_dicts = YAML(typ="safe").load(app_resp)

        if app_dicts:
            for app in app_dicts:
                try:
                    resources_dict = app["status"]["resources"]
                except KeyError:
                    continue

                for resource in resources_dict:
                    is_ready = False
                    if resource["kind"] == "StatefulSet":
                        name = app["metadata"]["name"]

                        # check if replicas ready
                        mani_resp = shell.run_command(
                            f"argocd app manifests {namespace}/{name} --source live",
                        )
                        for resource_manifest in mani_resp.split("---")[1:]:
                            manifest = YAML(typ="safe").load(resource_manifest)
                            if not manifest:
                                continue
                            kind = manifest["kind"]
                            resource_name = manifest["metadata"]["name"]
                            if kind == "StatefulSet" and resource_name == name:
                                try:
                                    is_ready = bool(manifest["status"]["readyReplicas"])
                                except (
                                    KeyError,
                                    TypeError,
                                ):  # Not ready if doesnt exist
                                    is_ready = False
                                time_stamp = datetime.strptime(
                                    manifest["metadata"]["creationTimestamp"],
                                    "%Y-%m-%dT%H:%M:%SZ",
                                )
                                service_data["name"].append(name)
                                service_data["version"].append(
                                    app["spec"]["source"]["targetRevision"]
                                )
                                service_data["ready"].append(is_ready)
                                service_data["deployed"].append(
                                    datetime.strftime(time_stamp, globals.TIME_FORMAT)
                                )

        services_df = polars.from_dict(service_data, schema=ServicesSchema)

        if running_only:
            services_df = services_df.filter(polars.col("ready").eq(True))
        return ServicesDataFrame(services_df)

    def _check_service(self, service_name: str):
        """
        validate that there is a app with the given service_name
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
                raise CommandError("Not authenticated to argocd server") from e
            elif "code = PermissionDenied" in str(e):
                raise CommandError(f"Target '{self._target}' not found") from e
            else:
                raise
