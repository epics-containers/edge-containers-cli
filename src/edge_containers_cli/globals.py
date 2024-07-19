import os
from pathlib import Path

import polars

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

# Set formatting of polars tables
polars.Config.set_tbl_hide_column_data_types(True)
polars.Config.set_tbl_hide_dataframe_shape(True)
polars.Config.set_tbl_rows(-1)
polars.Config.set_tbl_cols(-1)
polars.Config.set_fmt_str_lengths(82)
polars.Config.set_tbl_formatting("ASCII_MARKDOWN")
