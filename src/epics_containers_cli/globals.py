from dataclasses import dataclass
from enum import Enum


@dataclass
class Context:
    """Define a context for passing root parameters to sub-commands"""

    domain: str = ""
    kubernetes_namespace: str = ""
    beamline_repo: str = ""
    beamline_org: str = ""


class Architecture(str, Enum):
    linux = "linux"
    rtems = "rtems"
    arm = "arm"


class Targets(str, Enum):
    developer = "developer"
    runtime = "runtime"


# common stings used in paths
BEAMLINE_CHART_FOLDER = "beamline-chart"
CONFIG_FOLDER = "config"
IOC_CONFIG_FOLDER = "/epics/ioc/config/"
IOC_START = "/epics/ioc/start.sh"
IOC_NAME = "test-ioc"
