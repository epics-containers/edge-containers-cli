"""
utility functions
"""

import contextlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from ruamel.yaml import YAML

import edge_containers_cli.globals as globals
from edge_containers_cli.definitions import ENV
from edge_containers_cli.logging import log

T = TypeVar("T")


@contextlib.contextmanager
def chdir(path):
    """
    A simple wrapper around chdir(), it changes the current working directory
    upon entering and restores the old one on exit.
    """
    curdir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(curdir)


class TempDirManager:
    def __init__(self):
        self.debug = False
        self.dir = None

    def create(self) -> Path:
        self.dir = Path(tempfile.mkdtemp())
        return self.dir

    def cleanup(self) -> None:
        # keep the tmp folder if debug is enabled for inspection
        if not self.debug:
            shutil.rmtree(self.dir, ignore_errors=True)
        else:
            log.debug(f"Temporary directory {self.dir} retained")

    def __enter__(self):
        return self.create()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.cleanup()


tmpdir = TempDirManager()


def init_cleanup(debug: bool = False):
    tmpdir.debug = debug


def local_version() -> str:
    """
    create a CalVer style YYYY:MM:MICRO-b version where MICRO
    is derived from DD:HH:MM:SS in seconds in base 16
    """
    time_now = datetime.now()
    time_month = time_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elapsed = (time_now - time_month).seconds
    elapsed_base = hex(elapsed)[2:]
    return datetime.strftime(time_now, f"%Y.%-m.{elapsed_base}-b")


def public_methods(object: callable) -> list:
    public_list = []
    method_list = [func for func in dir(object) if callable(getattr(object, func))]
    for method in method_list:
        if method.startswith("_"):
            pass
        else:
            public_list.append(method)
    return public_list


def cache_dict(cache_dir: Path, cache_file: str, data_struc: dict) -> None:
    cache = cache_dir / cache_file
    cache.parent.mkdir(parents=True, exist_ok=True)
    with open(cache, "w") as f:
        f.write(json.dumps(data_struc, indent=4))


def read_cached_dict(cache_folder: Path, cache_file: str) -> dict:
    cache = cache_folder / cache_file
    read_dict = {}

    # Check cache if available
    if cache.exists():
        # Read from cache if not stale
        if (time.time() - os.path.getmtime(cache)) < globals.CACHE_EXPIRY:
            with open(cache) as f:
                read_dict = json.load(f)

    return read_dict


class ConfigController:
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self._variables: dict[str, Any] = {}
        self._yml = YAML(typ="safe")
        self._yml.indent()

    def _read_config(self) -> dict:
        if self.config_file.exists():
            with open(self.config_file) as fp:
                config_yaml = YAML(typ="safe").load(fp)
        else:
            config_yaml = {}
        return config_yaml

    def read_config(self):
        config = self._read_config()
        if config:  # Skip if empty
            for var in ENV:
                if var.value in config.keys():
                    read_var = config[var.value]
                    self._variables[var.value] = read_var

    def get_var(self, variable: ENV, default: T) -> T:
        if variable.value in self._variables.keys():
            return self._variables[variable]
        else:
            return default

    def store_config(self, context_name: str, input: dict[str, Any]):
        config = self._read_config()

        store = {}
        for var in ENV:
            if var.name in input.keys():
                store[var.value] = input[var.name]
        config[context_name] = store

        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as fp:
            YAML(typ="safe").dump(config, fp)

    def load_config(self, context_name: str):
        config = self._read_config()

        new_config = {}
        if context_name in config.keys():
            for key in config.keys():
                if type(config[key]) is dict:
                    new_config[key] = config[key]

            for var in ENV:
                if var.value in config[context_name].keys():
                    new_config[var.value] = config[context_name][var.value]

        with open(self.config_file, "w") as fp:
            YAML(typ="safe").dump(new_config, fp)

    def clear_config(self):
        config = self._read_config()

        new_config = {}
        for key in config.keys():
            if type(config[key]) is dict:
                new_config[key] = config[key]

        with open(self.config_file, "w") as fp:
            YAML(typ="safe").dump(new_config, fp)

    def get_contexts(self) -> list[str]:
        config = self._read_config()
        context_list = []
        for key in config.keys():
            if type(config[key]) is dict:
                context_list.append(key)
        return context_list
