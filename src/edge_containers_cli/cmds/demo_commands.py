"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""

import time
from datetime import datetime
from random import randrange, seed

import polars

from edge_containers_cli.cmds.commands import (
    CommandError,
    Commands,
    ServicesDataFrame,
    ServicesSchema,
)
from edge_containers_cli.definitions import ECContext
from edge_containers_cli.globals import TIME_FORMAT

DELAY = 2.0
NUM_SERVICES = 8
seed(237)


def process_t(time_string) -> str:
    time_stamp = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
    return datetime.strftime(time_stamp, TIME_FORMAT)


sample_data = {
    "name": [f"demo-ea-0{cnt}" for cnt in range(NUM_SERVICES)],
    "version": ["1.0." + str(25 - cnt) for cnt in range(NUM_SERVICES)],
    "ready": [True] * NUM_SERVICES,
    "deployed": [
        process_t(f"2024-10-22T11:23:0{randrange(1, 9)}Z")
        for cnt in range(NUM_SERVICES)
    ],
}

if NUM_SERVICES == 0:
    sample_ServicesDataFrame = polars.DataFrame(schema=ServicesSchema)
else:
    sample_ServicesDataFrame = ServicesDataFrame(polars.from_dict(sample_data))


def demo_wrapper():
    """Using closure to display once"""
    called = False

    def decorator(function):
        """Called selectively to avoid breaking autocompletion"""

        def wrapper(*args, **kwargs):
            nonlocal called
            if not called:
                called = True
                print("***RUNNING IN DEMO MODE***")
            return function(*args, **kwargs)

        return wrapper

    return decorator


demo_message = demo_wrapper()


class DemoCommands(Commands):
    """
    A class for implementing the Kubernetes based commands
    """

    def __init__(
        self,
        ctx: ECContext,
    ):
        self._target = "Demo Beamline"
        self._target_valid = False
        self._stateDF = sample_ServicesDataFrame

        self.lorem_min = 10
        self.lorem_max = 50
        self.lorem_step = 5
        self.lorem_count = self.lorem_min

    @demo_message
    def logs(self, service_name, prev):
        self._logs(service_name, prev)

    @demo_message
    def log_history(self, service_name):
        pass

    @demo_message
    def ps(self, running_only):
        self._ps(running_only)

    @demo_message
    def restart(self, service_name):
        self._stop(service_name, commit=False)
        self._start(service_name, commit=False)

    @demo_message
    def start(self, service_name, commit=False):
        self._start(service_name, commit=commit)

    def _start(self, service_name, commit=False):
        self._check_service(service_name)
        time.sleep(DELAY)
        self._stateDF = self._stateDF.with_columns(
            polars.when(polars.col("name") == service_name)
            .then(True)
            .otherwise(polars.col("ready"))
            .alias("ready")
        )

    @demo_message
    def stop(self, service_name, commit=False):
        self._stop(service_name, commit=commit)

    def _stop(self, service_name, commit=False):
        self._check_service(service_name)
        time.sleep(DELAY)
        self._stateDF = self._stateDF.with_columns(
            polars.when(polars.col("name") == service_name)
            .then(False)
            .otherwise(polars.col("ready"))
            .alias("ready")
        )

    def _get_logs(self, service_name, prev) -> str:
        self._check_service(service_name)
        if self.lorem_count < self.lorem_max:
            self.lorem_count += self.lorem_step
        else:
            self.lorem_count = self.lorem_min
        logs_list = ["Lorem ipsum dolor sit amet"] * self.lorem_count
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
            raise CommandError(
                f"Service '{service_name}' not found in '{self._target}'"
            )

    def _validate_target(self):
        pass
