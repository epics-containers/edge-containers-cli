"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""

from datetime import datetime
from edge_containers_cli.globals import TIME_FORMAT

import time

import polars

from edge_containers_cli.cmds.commands import CommandError, Commands, ServicesDataFrame
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.globals import TIME_FORMAT


DELAY = 2.0

def process_t(time_string) -> str:
    time_stamp = datetime.strptime(
                time_string, "%Y-%m-%dT%H:%M:%SZ"
            )
    return datetime.strftime(time_stamp, TIME_FORMAT)


sample_data = {
    "name": ["bl47p-ea-test-01", "bl47p-ea-test-02", "bl47p-ea-test-03"],  # type: ignore
    "version": ["2024.10.1", "2024.10.1b", "2024.10.1"],
    "ready": [True, True, False],
    "deployed": [process_t("2024-10-22T11:23:10Z"), process_t("2024-10-28T14:53:55Z"), process_t("2024-10-22T12:51:50Z")],
}
sample_ServicesDataFrame = ServicesDataFrame(polars.from_dict(sample_data))


class DemoCommands(Commands):
    """
    A class for implementing the Kubernetes based commands
    """

    def __init__(
        self,
        ctx: ECContext,
    ):
        #super().__init__(ctx)
        self._target = "Demo Beamline"
        self._target_valid = False
        self._stateDF = sample_ServicesDataFrame

    def logs(self, service_name, prev):
        self._logs(service_name, prev)

    def log_history(self, service_name):
        pass

    def ps(self, running_only):
        self._ps(running_only)

    def restart(self, service_name):
        self.stop(service_name)
        self.start(service_name)

    def start(self, service_name):
        self._check_service(service_name)
        time.sleep(DELAY)
        self._stateDF = self._stateDF.with_columns(
            polars.when(polars.col("name") == service_name).then(True).otherwise(polars.col("ready")).alias("ready")
        )

    def stop(self, service_name):
        self._check_service(service_name)
        time.sleep(DELAY)
        self._stateDF = self._stateDF.with_columns(
            polars.when(polars.col("name") == service_name).then(False).otherwise(polars.col("ready")).alias("ready")
        )

    def _get_logs(self, service_name, prev) -> str:
        self._check_service(service_name)
        logs_list = [f"logs for {service_name}:"] + ["Lorem ipsum"]*25
        return "\n".join(logs_list)

    def _get_services(self, running_only) -> ServicesDataFrame:
        if running_only:
            return ServicesDataFrame(self._stateDF.filter(polars.col("ready").eq(True)))
        else:
            return ServicesDataFrame(self._stateDF)

    def _check_service(self, service_name: str):
        """
        validate that there is a app with the given service_name
        """
        services_list = self._get_services(running_only=False)["name"]
        if service_name in services_list:
            pass
        else:
            raise CommandError(f"Service '{service_name}' not found in")

    def _validate_target(self):
        pass