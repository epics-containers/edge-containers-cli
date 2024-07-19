from pathlib import Path
from typing import Optional

import polars

from edge_containers_cli.definitions import ENV, ECContext
from edge_containers_cli.logging import log


class CommandError(Exception):
    pass


class Commands:
    """
    A base class for ec commands
    Implements the common functionality but defers specialist functions
    Allows the CLI or the TUI to call functions without worrying about backend
    """

    def __init__(self, ctx: ECContext):
        self._namespace = ctx.namespace
        self._namespace_valid = False
        self._repo = ctx.repo
        self._log_url = ctx.log_url

    @property
    def namespace(self):
        if not self._namespace_valid:  # Only validate once
            if self._namespace == ECContext().namespace:
                raise CommandError(
                    f"Please set {ENV.namespace.value} or pass --namespace"
                )
            else:
                self._validate_namespace()
                self._namespace_valid = True
        return self._namespace

    @property
    def repo(self):
        if self._repo == ECContext().repo:
            raise CommandError(f"Please set {ENV.repo.value} or pass --repo")
        else:
            return self._repo

    @property
    def log_url(self):
        if self._log_url == ECContext().log_url:
            raise CommandError(f"Please set {ENV.log_url.value} or pass --log_url")
        else:
            return self._log_url

    def attach(self, service_name):
        raise NotImplementedError

    def delete(self, service_name):
        raise NotImplementedError

    def deploy(self, service_name: str, version: str, args: str):
        raise NotImplementedError

    def deploy_local(self, svc_instance: Path, args: str):
        raise NotImplementedError

    def exec(self, service_name: str):
        raise NotImplementedError

    def logs(
        self, service_name: str, prev: bool, follow: bool, stdout: bool
    ) -> Optional[str | bool]:
        raise NotImplementedError

    def ps(self, running_only: bool, wide: bool):
        raise NotImplementedError

    def restart(self, service_name: str):
        raise NotImplementedError

    def start(self, service_name: str):
        raise NotImplementedError

    def stop(self, service_name: str):
        raise NotImplementedError

    def template(self, svc_instance: Path, args: str):
        raise NotImplementedError

    def _get_services(self, running_only: bool) -> polars.DataFrame:
        raise NotImplementedError

    def _ps(self, running_only: bool, wide: bool):
        """List all services in the current namespace"""
        services_df = self._get_services(running_only)
        if not wide:
            services_df.drop_in_place("image")
            log.debug(services_df)
        print(services_df)

    def _validate_namespace(self):
        pass

    def _all_services(self) -> list[str]:
        return []

    def _running_services(self) -> list[str]:
        return []
