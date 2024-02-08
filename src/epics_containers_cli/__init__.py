from importlib.metadata import version  # noqa

__version__ = version("epics-containers-cli")
del version

__all__ = ["__version__"]
