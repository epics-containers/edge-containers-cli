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
from typing import TypeVar

from ruamel.yaml import YAML

import edge_containers_cli.globals as globals
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


class WorkingDir:
    def __init__(self, debug: bool):
        self.debug = debug
        self.dir = None

    def create(self) -> Path:
        self.dir = Path(tempfile.mkdtemp())
        return self.dir

    def cleanup(self) -> None:
        # keep the tmp folder if debug is enabled for inspection
        if not self.debug and self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
        else:
            log.debug(f"Temporary directory {self.dir} retained")

    def __enter__(self):
        return self.create()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.cleanup()


class NewWorkingDir:
    def __init__(self):
        self.debug = False

    def __call__(self):
        return WorkingDir(self.debug)


new_workdir = NewWorkingDir()


def init_cleanup(debug: bool = False):
    new_workdir.debug = debug


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


def public_methods(object: object) -> list:
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


class YamlFile:
    def __init__(self, file: Path) -> None:
        self.file = file
        self._processor = YAML(typ="rt")  # 'rt' slower but preserves comments
        with open(file) as fp:
            self._yaml_data = self._processor.load(fp)

    def dump_file(self, output_path: Path | None = None):
        with open(output_path if output_path else self.file, "wb") as file_w:
            self._processor.dump(self._yaml_data, file_w)

    def get_key(self, key_path: str) -> str | bool | int | None:
        curser = self._yaml_data
        for key in key_path.split("."):
            try:
                curser = curser[key]
            except KeyError:
                log.debug(f"Entry '{key}' in '{key_path}' not found")
                return None
        return curser

    def set_key(self, key_path: str, value: str | bool | int):
        curser = self._yaml_data
        keys = key_path.split(".")
        element = keys[-1]

        # Iterate through mappings to element - Entries must exist
        for key in keys:
            if key is element:
                break  # Keep dict as pointer
            curser = curser[key]

        # Set element if exists or create it
        try:
            curser[element] = type(curser[element])(value)  # Preserve type
        except KeyError:
            # Create element if does not exist
            log.debug(f"Entry '{element}' in '{key_path}' not found - Creating")
            curser[element] = value

        log.debug(f"Set '{element}' in '{key_path}' to {value}")
