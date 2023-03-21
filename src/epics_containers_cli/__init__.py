from importlib.metadata import version

__version__ = version("epics-containers-cli")
del version

__all__ = ["__version__"]
