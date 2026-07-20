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

# argocd stamps every resource it manages with a tracking-id annotation of
# the form "<app-instance-name>:<group>/<kind>:<namespace>/<name>", e.g.
#   "i19-beamline_i19:argoproj.io/Application:i19-beamline/bl19i-ea-eiger-01"
TRACKING_ID_RE = re.compile(
    r"^(?P<owner>[^:]+):(?P<group>[^/]*)/(?P<kind>[^:]+):(?P<namespace>[^/]+)/(?P<name>.+)$"
)


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


async def _unset_key_and_children(target: str, key: str):
    cmd_unset = f"argocd app unset {target} -p {key}"
    await shell.run_command(cmd_unset, skip_on_dryrun=True)
    app_patches = await get_patches(target)
    for patch in app_patches:
        if re.match(rf"{key}\..*", patch["name"]):
            cmd_unset_child = f"argocd app unset {target} -p {patch['name']}"
            await shell.run_command(cmd_unset_child, skip_on_dryrun=True)


@do_retry
async def push_value(target: str, key: str, value: YamlTypes):
    # Get source details
    app_resp = await shell.run_command(
        f"argocd app get {target} -o yaml",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    repo_url = app_dicts["spec"]["source"]["repoURL"]
    path = Path(app_dicts["spec"]["source"]["path"])

    await set_value(repo_url, path / "values.yaml", key, value)

    # Free a possible patched value, its children & refresh repo
    await _unset_key_and_children(target, key)
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

    await del_key(repo_url, path / "values.yaml", key)

    # Free a possible patched value, its children & refresh repo
    await _unset_key_and_children(target, key)
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
            latest_version = await self._get_latest_version(service_name)
            version = latest_version

        service_path = Path(globals.SERVICES_DIR) / service_name
        if not await check_exists(service_path, self.repo, version):
            raise CommandError(
                f"Service '{service_name}' not found in repo "
                f"'{self.repo}' with branch/tag '{version}'"
            )

        if description is None:
            try:
                description = await self._check_description(service_name)
            except CommandError:
                # Service not yet deployed — no existing description to retrieve
                pass

        if confirm_callback:
            confirm_callback(version, description)
        deploy_dict: YamlTypes = {
            "enabled": True,
            "targetRevision": version,
            "labels": {"description": description},
        }

        await push_value(self.target, f"services.{service_name}", deploy_dict)

    async def logs(self, service_name, prev):
        await self._logs(service_name, prev)

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
        for manifest in YAML(typ="safe").load_all(mani_resp):
            if not isinstance(manifest, dict):
                continue
            if manifest.get("kind") not in ["StatefulSet", "Deployment"]:
                continue
            if manifest.get("metadata", {}).get("name") != service_name:
                continue
            return manifest

        raise CommandError(f"No manifest found for {service_name}")

    async def _check_stoppable(self, service_name) -> None:
        manifest = await self._get_service_manifest(service_name)

        labels = manifest["metadata"].get("labels")
        if not (labels and "enabled" in labels):
            raise CommandError(f"{service_name} does not support stop/start")

    async def _check_description(self, service_name) -> str | None:
        manifest = await self._get_service_manifest(service_name)

        # Return None if description doesn't exist or is ''
        return (
            val if (val := manifest["metadata"]["labels"].get("description")) else None
        )

    async def restart(self, service_name):
        await self._check_stoppable(service_name)
        namespace, app = extract_ns_app(self.target)
        cmd = f"argocd app delete-resource {namespace}/{service_name} --kind StatefulSet --all"
        await shell.run_command(cmd, skip_on_dryrun=True)

    async def start(self, service_name, commit=False):
        await self._check_stoppable(service_name)
        if commit:
            await push_value(self.target, f"services.{service_name}.enabled", True)
        else:
            await patch_value(self.target, f"services.{service_name}.enabled", True)

    async def stop(self, service_name, commit=False):
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

    async def _extract_app_manifests(self, app: dict, semaphore: asyncio.Semaphore):
        namespace, _ = extract_ns_app(self.target)

        service_data = {
            "name": [],  # type: ignore
            "label": [],
            "version": [],
            "ready": [],
            "deployed": [],
        }

        name = app.get("metadata", {}).get("name", "unknown")
        resources_dict = app.get("status", {}).get("resources", [])

        # an app-of-apps umbrella (e.g. "i19") owns nested child
        # Applications rather than a real workload - status.resources
        # reports each resource's kind directly from ArgoCD's own resource
        # tree, so we can detect and skip this without even fetching live
        # manifests, rather than inferring it from an absence of matches.
        if any(r.get("kind") == "Application" for r in resources_dict):
            return

        label = app.get("metadata", {}).get("labels", {}).get("device", "service")

        # ArgoCD already aggregates health across every resource it manages
        # for this Application (all StatefulSets, Services, ConfigMaps,
        # etc.) - if any child resource is degraded/missing, that's already
        # reflected here, the same way argocd-monitor reads
        # `status.health.status` directly rather than re-deriving it from
        # individual resources.
        health_status = app.get("status", {}).get("health", {}).get("status")
        is_ready = health_status == "Healthy"

        # start from the Application's own creation time, but a top-level
        # workload can be deleted and recreated independently of the
        # Application (e.g. `ec restart` deletes the StatefulSet and lets
        # ArgoCD recreate it on the next sync) - take the most recent of
        # the Application's and every matched workload's creationTimestamp
        # so this reflects the true "last activity" time, not just when
        # the Application itself was originally deployed.
        try:
            time_stamp = datetime.strptime(
                app.get("metadata", {}).get("creationTimestamp", ""),
                "%Y-%m-%dT%H:%M:%SZ",
            )
        except ValueError:
            time_stamp = datetime(1970, 1, 1)

        # the "description" label currently lives on the workload's own
        # manifest metadata, not the Application's - if that ever moves to
        # the Application itself this whole block (and the manifest fetch)
        # can go away in favour of just app["metadata"]["labels"]
        label_set = False
        if resources_dict:
            async with semaphore:
                mani_resp = await shell.run_command(
                    f"argocd app manifests {namespace}/{name} --source live",
                )
            for manifest in YAML(typ="safe").load_all(mani_resp):
                if not isinstance(manifest, dict):
                    continue

                # argocd stamps every live-managed resource with a
                # tracking-id annotation of the form
                #   "<owner>:<group>/<kind>:<namespace>/<name>"
                # <owner> is usually just the Application name, but for
                # Applications living outside the argocd control-plane
                # namespace (the "apps in any namespace" feature) it's
                # "<app-namespace>_<app-name>" instead - accept either.
                # Prefer this annotation when present, since it's robust to
                # fullnameOverride/chart naming conventions and confirms
                # ownership explicitly. `argocd app manifests <ns>/<app>`
                # is already scoped to this app though, so when the
                # annotation is absent (e.g. a hand-written test fixture,
                # or an older resource-tracking-method) fall back to the
                # manifest's own apiVersion to get the API group instead.
                tracking_id = (
                    manifest.get("metadata", {})
                    .get("annotations", {})
                    .get("argocd.argoproj.io/tracking-id", "")
                )
                match = TRACKING_ID_RE.match(tracking_id)
                if match is not None:
                    owner = match.group("owner")
                    if owner not in (name, f"{namespace}_{name}"):
                        continue
                    group = match.group("group")
                else:
                    api_version = manifest.get("apiVersion", "")
                    group = api_version.split("/", 1)[0] if "/" in api_version else ""

                # a top-level workload (Deployment/StatefulSet/DaemonSet)
                # lives in the "apps" API group. `argocd app manifests
                # --source live` only ever returns the app's own
                # tracked/desired resources (confirmed empirically - no
                # ReplicaSet/Pod ever appears in its output), so we don't
                # need an ownerReferences check to exclude runtime-spawned
                # children here.
                if group != "apps":
                    continue

                # take the label from the first top-level workload found -
                # if this app owns several, there isn't a meaningful way to
                # combine multiple description labels into one value
                if not label_set:
                    description = (
                        manifest.get("metadata", {})
                        .get("labels", {})
                        .get("description")
                    )
                    if description:
                        label = description
                        label_set = True

                try:
                    workload_ts = datetime.strptime(
                        manifest.get("metadata", {}).get("creationTimestamp", ""),
                        "%Y-%m-%dT%H:%M:%SZ",
                    )
                except ValueError:
                    workload_ts = datetime(1970, 1, 1)

                if workload_ts > time_stamp:
                    time_stamp = workload_ts

        service_data["name"].append(name)
        service_data["label"].append(label)
        service_data["version"].append(
            app.get("spec", {}).get("source", {}).get("targetRevision", "unknown")
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
        # 2 is just a backup for if for some reason cpu_count() returns None.
        # 2 would treat it like a dual-core system.
        cpus = os.cpu_count() or 2
        max_processes = 64
        sem = asyncio.Semaphore(min(cpus * 5, max_processes))

        await self._get_services()

        try:
            async with asyncio.TaskGroup() as group:
                for app in self.app_dicts:
                    group.create_task(self._extract_app_manifests(app, sem))
        except* ValueError as eg:
            for exc in eg.exceptions:
                print("Value Error:", exc)

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
