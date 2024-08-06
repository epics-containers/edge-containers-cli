import polars

from ._version import __version__

__all__ = ["__version__"]

# Set formatting of polars tables
polars.Config.set_tbl_hide_column_data_types(True)
polars.Config.set_tbl_hide_dataframe_shape(True)
polars.Config.set_tbl_rows(-1)
polars.Config.set_tbl_cols(-1)
polars.Config.set_fmt_str_lengths(82)
polars.Config.set_tbl_formatting("ASCII_MARKDOWN")
