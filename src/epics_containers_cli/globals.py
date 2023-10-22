import os
from dataclasses import dataclass
from enum import Enum


@dataclass
class Context:
    """Define a context for passing root parameters to sub-commands"""

    namespace: str = ""
    beamline_repo: str = ""


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
EC_DEBUG = os.environ.get("EC_DEBUG")
