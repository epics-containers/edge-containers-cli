"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""

import asyncio
import os
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from time import sleep

import polars
import typer
from ruamel.yaml import YAML

from edge_containers_cli import globals
from edge_containers_cli.cmds.commands import (
    CommandError,
    Commands,
    ServicesDataFrame,
    ServicesSchema,
)
from edge_containers_cli.definitions import ENV, ECContext
from edge_containers_cli.git import check_exists, del_key, set_value
from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError, shell
from edge_containers_cli.utils import YamlTypes, _AsyncFuncType, _run_async


def extract_ns_app(target: str) -> tuple[str, str]:
    namespace, app = target.split("/")
    return namespace, app


async def get_patches(target) -> dict:
    app_resp = await shell.run_command(
        f"argocd app get --show-params {target} -o json",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    try:
        patch_dict = app_dicts["spec"]["source"]["helm"]["parameters"]
    except KeyError:
        patch_dict = {}
    return patch_dict


def do_retry(cmd: _AsyncFuncType):
    async def _do_retry(*args, **kwargs):
        max_attempts = 5
        attempt = 1
        sleep_time = 1
        while attempt <= max_attempts:
            try:
                await cmd(*args, **kwargs)
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
async def patch_value(target: str, key: str, value: YamlTypes):
    cmd_temp_ = f"argocd app set {target} -p {key}={value}"
    await shell.run_command(cmd_temp_, skip_on_dryrun=True)
    # Rely on argocd autosync to get the cluster into the right state


@do_retry
async def push_value(target: str, key: str, value: YamlTypes):
    # Get source details
    app_resp = await shell.run_command(
        f"argocd app get {target} -o yaml",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    repo_url = app_dicts["spec"]["source"]["repoURL"]
    path = Path(app_dicts["spec"]["source"]["path"])

    set_value(repo_url, path / "values.yaml", key, value)

    # Free a possible patched value & refresh repo
    cmd_unset = f"argocd app unset {target} -p {key}"
    await shell.run_command(cmd_unset, skip_on_dryrun=True)
    cmd_refresh = f"argocd app get {target} --refresh"
    await shell.run_command(cmd_refresh, skip_on_dryrun=True)
    # Rely on argocd autosync to get the cluster into the right state


@do_retry
async def push_remove_key(target: str, key: str):
    # Get source details
    app_resp = await shell.run_command(
        f"argocd app get {target} -o yaml",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    repo_url = app_dicts["spec"]["source"]["repoURL"]
    path = Path(app_dicts["spec"]["source"]["path"])

    del_key(repo_url, path / "values.yaml", key)

    # Free a possible patched value, its children & refresh repo
    cmd_unset = f"argocd app unset {target} -p {key}"
    await shell.run_command(cmd_unset, skip_on_dryrun=True)
    app_patches = await get_patches(target)
    for patch in app_patches:
        if re.match(rf"{key}\..*", patch["name"]):
            cmd_unset_child = f"argocd app unset {target} -p {patch['name']}"
            await shell.run_command(cmd_unset_child, skip_on_dryrun=True)
    cmd_refresh = f"argocd app get {target} --refresh"
    await shell.run_command(cmd_refresh, skip_on_dryrun=True)
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

        self.app_dicts = {}
        self.services_df = polars.DataFrame()
        self.async_lock = asyncio.Lock()

    async def delete(self, service_name: str) -> None:
        await self._check_service(service_name)
        await push_remove_key(self.target, f"services.{service_name}")

    async def deploy(
        self, service_name, version, description, args, confirm_callback=None
    ) -> None:
        if not version:
            latest_version = self._get_latest_version(service_name)
            version = latest_version

        service_path = Path(globals.SERVICES_DIR) / service_name
        if not check_exists(service_path, self.repo, version):
            raise CommandError(
                f"Service '{service_name}' not found in repo "
                f"'{self.repo}' with branch/tag '{version}'"
            )

        if description is None:
            description = await self._check_description(service_name)

        if confirm_callback:
            confirm_callback(version, description)
        deploy_dict: YamlTypes = {
            "enabled": True,
            "targetRevision": version,
            "labels": {"description": description},
        }

        await push_value(self.target, f"services.{service_name}", deploy_dict)

    def logs(self, service_name, prev):
        self._logs(service_name, prev)

    async def log_history(self, service_name):
        await self._check_service(service_name)
        url = self.log_url.format(service_name=service_name)
        webbrowser.open(url)

    def ps(self, running_only):
        self._ps(running_only)

    async def _get_service_manifest(self, service_name) -> dict:
        await self._check_service(service_name)

        namespace, app = extract_ns_app(self.target)

        # get the manifests and determine if there is an 'enabled' label
        # which implies the service can be stopped/started
        mani_resp = await shell.run_command(
            f"argocd app manifests {namespace}/{service_name} --source live",
        )
        for resource_manifest in mani_resp.split("---")[1:]:
            manifest = YAML(typ="safe").load(resource_manifest)
            if not manifest:
                continue
            if manifest["kind"] not in ["StatefulSet", "Deployment"]:
                continue
            return manifest

        raise CommandError(f"No manifest found for {service_name}")

    async def _check_stoppable(self, service_name) -> None:
        stoppable = False

        manifest = await self._get_service_manifest(service_name)

        resource_name = manifest["metadata"]["name"]
        if resource_name == service_name:
            labels = manifest["metadata"].get("labels")
            if labels:
                stoppable = "enabled" in labels

        if not stoppable:
            raise CommandError(f"{service_name} does not support stop/start")

    async def _check_description(self, service_name) -> str | None:
        description = None

        manifest = await self._get_service_manifest(service_name)

        resource_name = manifest["metadata"]["name"]
        if resource_name == service_name:
            # This is to return None if description doesn't exist or is ''
            description = (
                val
                if (val := manifest["metadata"]["labels"].get("description"))
                else None
            )

        return description

    async def restart(self, service_name):
        await self._check_stoppable(service_name)
        namespace, app = extract_ns_app(self.target)
        cmd = (
            f"argocd app delete-resource {namespace}/{service_name} --kind StatefulSet"
        )
        await shell.run_command(cmd, skip_on_dryrun=True)

    async def start(self, service_name, commit=True):
        await self._check_stoppable(service_name)
        if commit:
            await push_value(self.target, f"services.{service_name}.enabled", True)
        else:
            await patch_value(self.target, f"services.{service_name}.enabled", True)

    async def stop(self, service_name, commit=True):
        await self._check_stoppable(service_name)
        if commit:
            await push_value(self.target, f"services.{service_name}.enabled", False)
        else:
            await patch_value(self.target, f"services.{service_name}.enabled", False)

    async def _get_logs(self, service_name, prev) -> str:
        namespace, app = extract_ns_app(self.target)
        await self._check_service(service_name)
        previous = "-p" if prev else ""

        logs = await shell.run_command(
            f"argocd app logs {namespace}/{service_name} {previous}",
            error_OK=True,
        )
        return logs

    async def _get_services(self) -> None:
        namespace, _ = extract_ns_app(self.target)
        app_resp = await shell.run_command(
            f"argocd app list --app-namespace {namespace} -o yaml",
        )
        self.app_dicts = YAML(typ="safe").load(app_resp)

    async def _extract_app_manifests(self, app: dict):
        namespace, _ = extract_ns_app(self.target)

        service_data = {
            "name": [],  # type: ignore
            "label": [],
            "version": [],
            "ready": [],
            "deployed": [],
        }

        try:
            resources_dict = app["status"]["resources"]
        except KeyError:
            return

        for resource in resources_dict:
            is_ready = False
            if resource["kind"] in ["StatefulSet", "Deployment"]:
                name = app["metadata"]["name"]

                try:
                    label = app["metadata"]["labels"]["device"]
                except KeyError:
                    label = "service"

                # check if replicas ready
                mani_resp = await shell.run_command(
                    f"argocd app manifests {namespace}/{name} --source live",
                )
                for resource_manifest in mani_resp.split("---")[1:]:
                    manifest = YAML(typ="safe").load(resource_manifest)
                    if not manifest:
                        continue
                    kind = manifest["kind"]
                    resource_name = manifest["metadata"]["name"]
                    if kind in ["StatefulSet", "Deployment"] and resource_name == name:
                        try:
                            label = manifest["metadata"]["labels"]["description"]
                        except KeyError:
                            label = "service"

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
                        service_data["label"].append(label)
                        service_data["version"].append(
                            app["spec"]["source"]["targetRevision"]
                        )
                        service_data["ready"].append(is_ready)
                        service_data["deployed"].append(
                            datetime.strftime(time_stamp, globals.TIME_FORMAT)
                        )

        service_df = polars.from_dict(service_data, schema=ServicesSchema)

        async with self.async_lock:
            if self.services_df.is_empty():
                self.services_df = service_df
            else:
                self.services_df.extend(service_df)

    async def _get_service_data(self):
        await self._get_services()

        async with asyncio.TaskGroup() as group:
            for app in self.app_dicts:
                group.create_task(self._extract_app_manifests(app))

    def _get_services_df(self, running_only) -> ServicesDataFrame:
        # Clear the current dataframe before polling the current manifests
        self.services_df = self.services_df.clear()

        # Helper function being used to help run asynchronously
        _run_async(self._get_service_data())

        services_df = self.services_df

        if running_only:
            services_df = services_df.filter(polars.col("ready").eq(True))
        return ServicesDataFrame(services_df)

    async def _check_service(self, service_name: str):
        """
        validate that there is a app with the given service_name
        """
        await self._get_services()
        services_list = [app["metadata"]["name"] for app in self.app_dicts]
        if service_name in services_list:
            pass
        else:
            raise CommandError(f"Service '{service_name}' not found in {self.target}")

    async def _validate_target(self):
        """
        Verify we have a good namespace that exists in the cluster
        """
        retries = 2

        cmd = f"argocd app get {self._target}"
        try:
            await shell.run_command(cmd, error_OK=False)
        except ShellError as e:
            if "Unauthenticated" in str(e) or "unspecified" in str(e):
                retries -= 1
                login = os.environ.get(ENV.login.value)
                if retries <= 0 or not login:
                    raise CommandError("Not authenticated to argocd server") from e

                # try to log in
                if not login or not typer.confirm("Login to ArgoCD?", default=True):
                    raise typer.Abort() from e
                await shell.run_command(login, error_OK=False, skip_on_dryrun=True)

                # retry validation
                await self._validate_target()

            elif "code = PermissionDenied" in str(e):
                raise CommandError(f"Target '{self._target}' not found") from e
            else:
                raise
