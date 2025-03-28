from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

import polars
from natsort import natsorted

from edge_containers_cli import globals
from edge_containers_cli.definitions import ENV, ECContext
from edge_containers_cli.git import create_version_map
from edge_containers_cli.logging import log
from edge_containers_cli.utils import new_workdir


class CommandError(Exception):
    pass


ServicesSchema = polars.Schema(
    {
        "name": polars.String,  # type: ignore
        "version": polars.String,
        "ready": polars.Boolean,
        "deployed": polars.String,
    }
)


class ServicesDataFrame(polars.DataFrame):
    def __init__(self, data: polars.DataFrame):
        super().__init__(data)
        expected_schema = ServicesSchema
        if self.schema != expected_schema:
            raise ValueError(
                f"DataFrame schema: {self.schema} does not match expected schema: {expected_schema}"
            )


class Commands(ABC):
    """
    A base class for ec commands
    Implements the common functionality but defers specialist functions
    Allows the CLI or the TUI to call functions without worrying about backend
    Methods not exposed to the CLI should be private
    """

    params_opt_out: dict[str, list[str]] = {}  # Drop parameters from the CLI
    params_optional: dict[str, list[str]] = {}  # Set optional parameters from the CLI

    def __init__(self, ctx: ECContext):
        self._target = ctx.target
        self._target_valid = False
        self._repo = ctx.repo
        self._log_url = ctx.log_url

    def __getattribute__(self, attr_name):
        """Override to wrap each abstract method"""
        attr = super().__getattribute__(attr_name)
        if callable(attr):
            if attr_name[0] == "_":
                log_f = log.debug
            else:
                log_f = log.info

            def wrapper(*args, **kwargs):
                call_msg = (
                    f"Calling: {attr_name} {', '.join(str(item) for item in args)}"
                )
                return_msg = (
                    f"Returned: {attr_name} {', '.join(str(item) for item in args)}"
                )
                if kwargs:
                    call_msg = f"{call_msg} [{', '.join(f'{k}={v}' for k, v in kwargs.items())}]"
                    return_msg = f"{return_msg} [{', '.join(f'{k}={v}' for k, v in kwargs.items())}]"
                log_f(call_msg)
                result = attr(*args, **kwargs)
                log_f(return_msg)
                return result

            return wrapper
        else:
            return attr

    @property
    def target(self):
        if not self._target_valid:  # Only validate once
            if self._target == ECContext().target:
                raise CommandError(f"Please set {ENV.target.value} or pass --target")
            else:
                self._validate_target()
                self._target_valid = True
        log.debug("target = %s", self._target)
        return self._target

    @property
    def repo(self):
        if self._repo == ECContext().repo:
            raise CommandError(f"Please set {ENV.repo.value} or pass --repo")
        else:
            log.debug("repo = %s", self._repo)
            return self._repo

    @property
    def log_url(self):
        if self._log_url == ECContext().log_url:
            raise CommandError(f"Please set {ENV.log_url.value} or pass --log_url")
        else:
            log.debug("log_url = %s", self._log_url)
            return self._log_url

    def attach(self, service_name: str) -> None:
        raise NotImplementedError

    def delete(self, service_name: str) -> None:
        raise NotImplementedError

    def deploy(
        self,
        service_name: str,
        version: str,
        args: str,
        confirm_callback: Callable[[str], None] | None = None,
    ) -> None:
        raise NotImplementedError

    def deploy_local(
        self,
        svc_instance: Path,
        args: str,
        confirm_callback: Callable[[str], None] | None = None,
    ) -> None:
        raise NotImplementedError

    def exec(self, service_name: str) -> None:
        raise NotImplementedError

    def logs(self, service_name: str, prev: bool) -> None:
        raise NotImplementedError

    def log_history(self, service_name: str) -> None:
        raise NotImplementedError

    def ps(self, running_only: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def restart(self, service_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def start(self, service_name: str, commit: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self, service_name: str, commit: bool = False) -> None:
        raise NotImplementedError

    def template(self, svc_instance: Path, args: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def _get_services(self, running_only: bool) -> ServicesDataFrame:
        raise NotImplementedError

    def _ps(self, running_only: bool) -> None:
        services_df = self._get_services(running_only)
        print(services_df)

    @abstractmethod
    def _get_logs(self, service_name: str, prev: bool) -> str:
        raise NotImplementedError

    def _logs(self, service_name: str, prev: bool) -> None:
        print(self._get_logs(service_name, prev))

    def _validate_target(self) -> None:
        raise NotImplementedError

    def _running_services(self) -> list[str]:
        return self._get_services(running_only=True)["name"].to_list()

    def _all_services(self) -> list[str]:
        return self._get_services(running_only=False)["name"].to_list()

    def _check_service(self, service_name: str) -> None:
        services_list = self._get_services(running_only=False)["name"]
        if service_name in services_list:
            pass
        else:
            raise CommandError(f"Service '{service_name}' not found in {self.target}")

    def _get_latest_version(self, service_name) -> str:
        with new_workdir() as path:
            version_map = create_version_map(
                self.repo,
                Path(globals.SERVICES_DIR),
                path,
                shared_files=[globals.SHARED_VALUES],
            )
        svc_list = version_map.keys()
        log.debug(f"Found the following services: {svc_list}")
        if service_name not in svc_list:
            raise CommandError(f"Service '{service_name}' not found in {self.repo}")

        version_list = natsorted(version_map[service_name])
        log.debug(f"Found the following versions of {service_name}: {version_list}")
        try:
            version = version_list[-1]
        except IndexError as err:
            raise CommandError(
                f"No versions of '{service_name}' found in {self.repo}"
            ) from err

        return version
