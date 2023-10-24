import os
from dataclasses import dataclass
from enum import Enum


@dataclass
class Context:
    """Define a context for passing root parameters to sub-commands"""

    namespace: str = ""
    beamline_repo: str = ""
    verbose: bool = False
    debug: bool = False


class Architecture(str, Enum):
    linux = "linux"
    rtems = "rtems"
    arm = "arm"

    def __str__(self):
        return str(self.value)


class Targets(str, Enum):
    developer = "developer"
    runtime = "runtime"

    def __str__(self):
        return str(self.value)


# common stings used in paths
BEAMLINE_CHART_FOLDER = "beamline-chart"
CONFIG_FOLDER = "config"
IOC_CONFIG_FOLDER = "/epics/ioc/config/"
IOC_START = "/epics/ioc/start.sh"
IOC_NAME = "test-ioc"
# these should be set to 0 or 1 in the environment - blank is treated as false
EC_DEBUG = bool(os.environ.get("EC_DEBUG"))
EC_VERBOSE = bool(os.environ.get("EC_VERBOSE"))

EC_REGISTRY_MAPPING = os.environ.get(
    "EC_REGISTRY_MAPPING",
    "github.com=ghcr.io gitlab.diamond.ac.uk=gcr.io/diamond-privreg/controls/ioc",
)
EC_CONTAINER_CLI = os.environ.get("EC_CONTAINER_CLI")  # default to auto choice
EC_LOG_URL = os.environ.get("EC_LOG_URL", None)
