import os
from pathlib import Path

# common stings used in paths
# location for config
CONFIG_ROOT = Path(os.path.expanduser("~/.config/edge-containers-cli/"))
# available enviroment
ENV_CONFIG = "settings.yaml"
# location for caching
CACHE_ROOT = Path(os.path.expanduser("~/.cache/edge-containers-cli/"))
# available ioc cache
SERVICE_CACHE = "service.json"
# cache expiry time in seconds
CACHE_EXPIRY = 15
# services directory
SERVICES_DIR = "services"
# Shared values
SHARED_VALUES = "services/values.yaml"
# Time formatting
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
