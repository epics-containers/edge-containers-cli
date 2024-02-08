from importlib.metadata import version  # noqa

__version__ = version("ec-cli")
del version

__all__ = ["__version__"]
