from pathlib import Path
from abc import ABC, abstractmethod
import polars

from edge_containers_cli.definitions import ENV, ECContext
from edge_containers_cli.logging import log

class CommandError(Exception):
    pass


ServicesSchema = polars.Schema({
    'name': polars.String,
    'version': polars.String,
    'running': polars.Boolean,
    'restarts': polars.Int64,
    'deployed': polars.String,
    'image': polars.String,
})

class ServicesDataFrame(polars.DataFrame):
    def __init__(self, data: polars.DataFrame):
        super().__init__(data)
        expected_schema = ServicesSchema
        if self.schema != expected_schema:
            raise ValueError(f"DataFrame schema: {self.schema} does not match expected schema: {expected_schema}")


class Commands(ABC):
    """
    A base class for ec commands
    Implements the common functionality but defers specialist functions
    Allows the CLI or the TUI to call functions without worrying about backend
    """

    def __init__(self, ctx: ECContext):
        self._target = ctx.target
        self._target_valid = False
        self._repo = ctx.repo
        self._log_url = ctx.log_url

    @property
    def target(self):
        if not self._target_valid:  # Only validate once
            if self._target == ECContext().target:
                raise CommandError(
                    f"Please set {ENV.target.value} or pass --target"
                )
            else:
                self._validate_target()
                self._target_valid = True
        return self._target

    @property
    def repo(self):
        if self._repo == ECContext().repo:
            raise CommandError(
                f"Please set {ENV.repo.value} or pass --repo"
                )
        else:
            return self._repo

    @property
    def log_url(self):
        if self._log_url == ECContext().log_url:
            raise CommandError(
                f"Please set {ENV.log_url.value} or pass --log_url"
                )
        else:
            return self._log_url

    def attach(self, service_name: str):
        raise NotImplementedError

    def delete(self, service_name: str):
        raise NotImplementedError

    def deploy(self, service_name: str, version: str, args: str):
        raise NotImplementedError

    def deploy_local(self, svc_instance: Path, args: str):
        raise NotImplementedError

    def exec(self, service_name: str):
        raise NotImplementedError

    def logs(self, service_name: str, prev: bool):
        raise NotImplementedError
    
    def log_history(self, service_name: str):
        raise NotImplementedError

    def ps(self, running_only: bool, wide: bool):
        raise NotImplementedError

    @abstractmethod
    def restart(self, service_name: str):
        raise NotImplementedError

    @abstractmethod
    def start(self, service_name: str):
        raise NotImplementedError

    @abstractmethod
    def stop(self, service_name: str):
        raise NotImplementedError

    def template(self, svc_instance: Path, args: str):
        raise NotImplementedError

    @abstractmethod
    def _get_services(self, running_only: bool) -> ServicesDataFrame:
        raise NotImplementedError

    def _ps(self, running_only: bool, wide: bool):
        services_df = self._get_services(running_only)
        if not wide:
            services_df.drop_in_place("image")
            log.debug(services_df)
        print(services_df)

    @abstractmethod
    def _get_logs(self, service_name: str, prev: bool) -> str:
        raise NotImplementedError

    def _logs(self, service_name: str, prev: bool):
        print(self._get_logs(service_name, prev))

    def _validate_target(self):
        pass

    def _all_services(self) -> list[str]:
        return []

    def _running_services(self) -> list[str]:
        return []
