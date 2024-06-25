import os
from dataclasses import dataclass

import polars


@dataclass
class Context:
    """Define a context for passing root parameters to sub-commands"""

    namespace: str = ""
    beamline_repo: str = ""
    verbose: bool = False
    debug: bool = False


# common stings used in paths
# folder containing the beamline IOC Instance Helm Chart
SHARED_CHARTS_FOLDER = "../../helm"
# location of IOC Instance configuration in a beamline ioc Instance folder
CONFIG_FOLDER = "config"
# location of IOC Instance configuration inside a Generic IOC container
IOC_CONFIG_FOLDER = "/epics/ioc/config/"
# location of IOC Instance configuration inside a Generic IOC container
IOC_RUNTIME_FOLDER = "/epics/runtime/"
# file name of IOC Instance ibek configuration inside a Generic IOC container
CONFIG_FILE_GLOB = "*.yaml"
# namespace name for deploying IOC instances into the local podman/docker
LOCAL_NAMESPACE = "local"
# location for caching
CACHE_ROOT = os.path.expanduser("~/.cache/edge-containers-cli/")
# available ioc cache
IOC_CACHE = "ioc_cache.json"
# cache expiry time in seconds
CACHE_EXPIRY = 15

# these should be set to 0 or 1 in the environment - blank is treated as false
# Enable debug logging in all ec commands
EC_DEBUG = bool(os.environ.get("EC_DEBUG", 0))
# Enable printing of all shell commands run by ec
EC_VERBOSE = bool(os.environ.get("EC_VERBOSE", 0))

EC_CONTAINER_CLI = os.environ.get("EC_CONTAINER_CLI")  # default to auto choice
EC_SERVICES_REPO = os.environ.get("EC_SERVICES_REPO", "")
EC_K8S_NAMESPACE = os.environ.get("EC_K8S_NAMESPACE", "")
EC_LOG_URL = os.environ.get("EC_LOG_URL", None)

# Set formatting of polars tables
polars.Config.set_tbl_hide_column_data_types(True)
polars.Config.set_tbl_hide_dataframe_shape(True)
polars.Config.set_tbl_rows(-1)
polars.Config.set_tbl_cols(-1)
polars.Config.set_fmt_str_lengths(82)
polars.Config.set_tbl_formatting("ASCII_MARKDOWN")
