"""
implements commands for deploying and managing service instances suing argocd

Relies on the Helm class for deployment aspects.
"""

import time
from datetime import datetime
from random import randrange, seed

import polars

from edge_containers_cli.cmds.commands import (
    HEALTHY,
    STOPPED_SUFFIX,
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
    "health": [HEALTHY] * NUM_SERVICES,
    "sync": ["Synced"] * NUM_SERVICES,
    "version": ["1.0." + str(25 - cnt) for cnt in range(NUM_SERVICES)],
    "last sync": [
        process_t(f"2024-10-22T11:23:0{randrange(1, 9)}Z")
        for cnt in range(NUM_SERVICES)
    ],
    "description": [f"demo-device-0{cnt}" for cnt in range(NUM_SERVICES)],
    "properties": [f"location=bench-{cnt % 2}" for cnt in range(NUM_SERVICES)],
}

if NUM_SERVICES == 0:
    SampleServicesDataFrame = polars.DataFrame(schema=ServicesSchema)
else:
    SampleServicesDataFrame = ServicesDataFrame(
        polars.from_dict(sample_data, schema=ServicesSchema)
    )


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
        # the base class records repo / log_url from the context - without
        # this the demo backend has no _repo or _log_url and any command
        # using them fails with AttributeError instead of the intended
        # "Please set ..." message (and ignores --repo / --log_url).
        super().__init__(ctx)
        self._target = "Demo Beamline"
        self._stateDF = SampleServicesDataFrame

        self.lorem_min = 10
        self.lorem_max = 50
        self.lorem_step = 5
        self.lorem_count = self.lorem_min

    @demo_message
    async def logs(self, service_name, prev):
        await self._logs(service_name, prev)

    @demo_message
    async def log_history(self, service_name):
        pass

    @demo_message
    def ps(self, running_only, wide=False):
        self._ps(running_only, wide)

    @demo_message
    async def restart(self, service_name):
        await self._stop(service_name, commit=False)
        await self._start(service_name, commit=False)

    @demo_message
    async def set_description(self, service_name, description, confirm_callback=None):
        # Descriptions are stored as an Argo CD Application annotation -
        # the demo backend has no such store, so there's nothing to
        # persist here. Still validate the service and run the same
        # confirmation flow as the real backends, so `ec set-desc` behaves
        # consistently in demo mode instead of silently doing nothing.
        await self._check_service(service_name)
        if confirm_callback:
            confirm_callback(None, description)

    @demo_message
    async def start(self, service_name, commit=False):
        await self._start(service_name, commit=commit)

    async def _start(self, service_name, commit=False):
        await self._check_service(service_name)
        time.sleep(DELAY)
        self._stateDF = self._stateDF.with_columns(
            polars.when(polars.col("name") == service_name)
            .then(polars.lit(HEALTHY))
            .otherwise(polars.col("health"))
            .alias("health")
        )

    @demo_message
    async def stop(self, service_name, commit=False):
        await self._stop(service_name, commit=commit)

    async def _stop(self, service_name, commit=False):
        await self._check_service(service_name)
        time.sleep(DELAY)
        self._stateDF = self._stateDF.with_columns(
            polars.when(polars.col("name") == service_name)
            .then(polars.lit(HEALTHY + STOPPED_SUFFIX))
            .otherwise(polars.col("health"))
            .alias("health")
        )

    async def _get_logs(self, service_name, prev) -> str:
        await self._check_service(service_name)
        if self.lorem_count < self.lorem_max:
            self.lorem_count += self.lorem_step
        else:
            self.lorem_count = self.lorem_min
        logs_list = ["Lorem ipsum dolor sit amet"] * self.lorem_count
        return "\n".join(logs_list)

    def _get_services_df(self, running_only) -> ServicesDataFrame:
        if running_only:
            return ServicesDataFrame(
                self._stateDF.filter(polars.col("health").eq(HEALTHY))
            )
        else:
            return ServicesDataFrame(self._stateDF)

    async def _check_service(self, service_name: str):
        """
        validate that there is a app with the given service_name
        """
        services_list = self._get_services_df(running_only=False)["name"]
        if service_name in services_list:
            pass
        else:
            raise CommandError(
                f"Service '{service_name}' not found in '{self._target}'"
            )

    async def _validate_target(self):
        pass
