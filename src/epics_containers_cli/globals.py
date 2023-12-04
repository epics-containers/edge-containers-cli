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
# folder containing the beamline IOC Instance Helm Chart
BEAMLINE_CHART_FOLDER = "beamline-chart"
# location of IOC Instance configuration in a beamline ioc Instance folder
CONFIG_FOLDER = "config"
# location of IOC Instance configuration inside a Generic IOC container
IOC_CONFIG_FOLDER = "/epics/ioc/config/"
# file name of IOC Instance ibek configuration inside a Generic IOC container
CONFIG_FILE_GLOB = "*.yaml"
# location of default IOC start script inside Generic IOC containers
IOC_START = "/epics/ioc/start.sh"
# default container name for local testing
IOC_NAME = "test-ioc"
# namespace name for deploying IOC instances into the local podman/docker
LOCAL_NAMESPACE = "local"

# these should be set to 0 or 1 in the environment - blank is treated as false
# Enable debug logging in all ec commands
EC_DEBUG = bool(os.environ.get("EC_DEBUG", 0))
# Enable printing of all shell commands run by ec
EC_VERBOSE = bool(os.environ.get("EC_VERBOSE", 0))

"""
each mapping is a string of the form <source registry>=<container registry>
the container registry is used to build the image name as
<container registry>/<source organisation>/<repo name (without .git)>:<tag>
mappings are separated by space or line break.

For a much more flexible way to define mappings see EC_REGISTRY_MAPPING_REGEX
"""
EC_REGISTRY_MAPPING = os.environ.get(
    "EC_REGISTRY_MAPPING",
    "github.com=ghcr.io",
)

"""
each mapping is a regex to match the repo name and a replacement string
to generate the container registry name. Mappings are separated by line
break and regex and replacement are separated by space
"""
EC_REGISTRY_MAPPING_REGEX = os.environ.get(
    "EC_REGISTRY_MAPPING_REGEX",
    r"""
.*github.com:(.*)\/(.*) ghcr.io/\1/\2
.*gitlab.diamond.ac.uk.*\/(.*) gcr.io/diamond-privreg/controls/prod/ioc/\1
""",
)

EC_CONTAINER_CLI = os.environ.get("EC_CONTAINER_CLI")  # default to auto choice
EC_LOG_URL = os.environ.get("EC_LOG_URL", None)
