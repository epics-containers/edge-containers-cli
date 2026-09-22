"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""

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
    HEALTHY,
    STOPPED_SUFFIX,
    CommandError,
    Commands,
    ServicesDataFrame,
    ServicesSchema,
)
from edge_containers_cli.definitions import ENV, ECContext
from edge_containers_cli.git import check_exists, del_key, set_value, set_values
from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError, shell
from edge_containers_cli.utils import YamlTypes, _AsyncFuncType, _run_async

# fixed contract with the argocd-apps helm chart and the values-repo schema:
# the chart renders a service's `description` value as this annotation on
# the per-service Application's own metadata.
DESCRIPTION_ANNOTATION = "epics-containers.github.io/description"

# Application labels left out of the `properties` column, and label key
# prefixes stripped for brevity - both as argocd-monitor does
# (src/components/app-table/columns.tsx). STOPPED is shown in `health`
# instead.
STOPPED_LABEL = "STOPPED"
HIDDEN_LABELS = {"argocd.argoproj.io/instance", STOPPED_LABEL}
STRIP_LABEL_PREFIXES = ["argocd.argoproj.io/"]


def _format_label_key(key: str) -> str:
    for prefix in STRIP_LABEL_PREFIXES:
        if key.startswith(prefix):
            return key.removeprefix(prefix)
    return key


def _format_time(time_string: str) -> str:
    try:
        time_stamp = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return time_string
    return datetime.strftime(time_stamp, globals.TIME_FORMAT)


def app_to_row(app: dict) -> dict[str, str] | None:
    """
    Turn one Application from `argocd app list` into a row of `ec ps`,
    reading only the Application itself - never its live resources. Returns
    None for an app-of-apps umbrella, which is not a service.
    """
    metadata = app.get("metadata") or {}
    spec = app.get("spec") or {}
    status = app.get("status") or {}
    labels = metadata.get("labels") or {}
    annotations = metadata.get("annotations") or {}

    # an app-of-apps umbrella (e.g. "i19") owns nested child Applications
    # rather than a workload. status.resources lists each managed
    # resource's kind, so it can be skipped without any further lookup.
    resources = status.get("resources") or []
    if any(r.get("kind") == "Application" for r in resources):
        return None

    # Argo CD already aggregates health across every resource the
    # Application manages. The argocd-apps chart sets the STOPPED label on
    # a service stopped with `ec stop`, which argocd-monitor shows as a
    # badge next to the health.
    health = (status.get("health") or {}).get("status") or "Unknown"
    if labels.get(STOPPED_LABEL):
        health += STOPPED_SUFFIX

    # `ec restart` deletes the StatefulSet, and only Argo CD's automated
    # self-heal sync brings it back - so a restart shows here as a new
    # sync operation, and needs no lookup of the live StatefulSet.
    finished_at = (status.get("operationState") or {}).get("finishedAt") or ""

    properties = " ".join(
        f"{_format_label_key(key)}={value}"
        for key, value in labels.items()
        if key not in HIDDEN_LABELS
    )

    return {
        "name": metadata.get("name", "unknown"),
        "health": health,
        "sync": (status.get("sync") or {}).get("status") or "Unknown",
        "version": (spec.get("source") or {}).get("targetRevision", "unknown"),
        "last sync": _format_time(finished_at),
        # the description is an annotation on the Application (see
        # DESCRIPTION_ANNOTATION), empty when unset
        "description": annotations.get(DESCRIPTION_ANNOTATION) or "",
        "properties": properties,
    }


# feature -> (chart dependency, minimum version). An old argocd-apps chart
# rejects a key its schema doesn't know about, which breaks the root app
# and stops every service on the deployment syncing - so a feature that
# depends on a newer argocd-apps must gate its write on this table via
# push_values(..., require_chart_version=(*CHART_VERSION_GATES[...], feature)).
# Extend this table, not check_chart_dependency_version, when the next
# feature needs a floor.
CHART_VERSION_GATES: dict[str, tuple[str, str]] = {
    # ec-helm-charts#122: 5.10.0 is the first argocd-apps release that
    # renders `description` - 5.8.0 and 5.9.0 shipped without it.
    "description": ("argocd-apps", "5.10.0"),
}


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
async def push_values(
    target: str,
    keys: dict[str, YamlTypes],
    require_keys: list[str] | None = None,
    require_chart_version: tuple[str, str, str] | None = None,
):
    """
    Like push_value, but sets several keys in a single commit. Any key
    not present in `keys` is left untouched in the values repo, so a
    caller only ever writes the fields it was asked to change.

    `require_keys`, if given, must already exist in the values repo or
    nothing is written/committed/pushed - see set_values.

    `require_chart_version`, if given, is (dependency, min_version,
    feature) - see set_values.
    """
    # Get source details
    app_resp = await shell.run_command(
        f"argocd app get {target} -o yaml",
    )
    app_dicts = YAML(typ="safe").load(app_resp)
    repo_url = app_dicts["spec"]["source"]["repoURL"]
    path = Path(app_dicts["spec"]["source"]["path"])

    await set_values(
        repo_url,
        path / "values.yaml",
        keys,
        require_keys=require_keys,
        require_chart_version=require_chart_version,
    )

    # Free any possible patched values, their children & refresh repo
    for key in keys:
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

        self.app_dicts: list[dict] = []

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

        # description is for the confirm-prompt display only here - never
        # written back unless --desc was actually given.
        display_description = description
        if display_description is None:
            try:
                display_description = await self._get_description(service_name)
            except CommandError:
                # Service not yet deployed — no existing description to show
                pass

        if confirm_callback:
            confirm_callback(version, display_description)

        # Only write the keys we were asked to change - any other
        # per-service metadata in the values repo (including any labels,
        # or fields added in future) must survive a deploy untouched.
        deploy_dict: dict[str, YamlTypes] = {
            f"services.{service_name}.enabled": True,
            f"services.{service_name}.targetRevision": version,
        }
        # only gate the write on the argocd-apps chart version when a
        # description is actually being written - a version-only deploy
        # must work regardless of how old the deployment's argocd-apps
        # dependency is.
        require_chart_version = None
        if description is not None:
            # `--desc ""` explicitly clears the description. Never push
            # `labels` - the description is now an Application annotation,
            # not a label.
            deploy_dict[f"services.{service_name}.description"] = description
            require_chart_version = (*CHART_VERSION_GATES["description"], "description")

        await push_values(
            self.target, deploy_dict, require_chart_version=require_chart_version
        )

    async def set_description(
        self, service_name: str, description: str, confirm_callback=None
    ) -> None:
        # Only ever touches the description leaf key - never enabled or
        # targetRevision, so this can never roll the service to another
        # version or change whether it's enabled.
        display_description = None
        try:
            display_description = await self._get_description(service_name)
        except CommandError:
            # Service not yet deployed - push_values below refuses anyway,
            # since there's no services.<name> entry to update.
            pass

        if confirm_callback:
            confirm_callback(display_description, description)

        parent_key = f"services.{service_name}"
        await push_values(
            self.target,
            {f"{parent_key}.description": description},
            require_keys=[parent_key],
            require_chart_version=(*CHART_VERSION_GATES["description"], "description"),
        )

    async def logs(self, service_name, prev):
        await self._logs(service_name, prev)

    async def log_history(self, service_name):
        await self._check_service(service_name)
        url = self.log_url.format(service_name=service_name)
        webbrowser.open(url)

    def ps(self, running_only, wide=False):
        self._ps(running_only, wide)

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

    async def _get_description(self, service_name) -> str | None:
        await self._check_service(service_name)
        namespace, _ = extract_ns_app(self.target)

        app_resp = await shell.run_command(
            f"argocd app get {namespace}/{service_name} -o yaml",
        )
        app_dict = YAML(typ="safe").load(app_resp)

        # Return None if the annotation doesn't exist or is ''
        annotations = app_dict.get("metadata", {}).get("annotations", {})
        return val if (val := annotations.get(DESCRIPTION_ANNOTATION)) else None

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

    def _get_services_df(self, running_only) -> ServicesDataFrame:
        # Everything `ps` shows comes from this single `argocd app list`,
        # however many services there are - the same way argocd-monitor
        # builds its Applications table from one GET /api/v1/applications.
        _run_async(self._get_services())

        rows = [row for app in self.app_dicts or [] if (row := app_to_row(app))]
        services_df = polars.DataFrame(rows, schema=ServicesSchema)

        if running_only:
            services_df = services_df.filter(polars.col("health").eq(HEALTHY))
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
