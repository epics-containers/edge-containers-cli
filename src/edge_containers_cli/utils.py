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
from typing import Union

from ruamel.yaml import YAML, scalarint

import edge_containers_cli.globals as globals
from edge_containers_cli.logging import log

YamlPrimatives = Union[str, bool, int, None]
YamlTypes = Union[YamlPrimatives, dict[str, YamlPrimatives]]


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


class YamlFileError(Exception):
    pass


class YamlFile:
    def __init__(self, file: Path) -> None:
        self.file = file
        self._processor = YAML(typ="rt")  # 'rt' slower but preserves comments
        with open(file) as fp:
            self._yaml_data = self._processor.load(fp)

    def dump_file(self, output_path: Path | None = None):
        with open(output_path if output_path else self.file, "wb") as file_w:
            self._processor.dump(self._yaml_data, file_w)

    def get_key(self, key_path: str) -> YamlTypes:
        curser = self._yaml_data
        prev_key = ""
        for key in key_path.split("."):
            try:
                curser = curser[key]
            except KeyError as e:
                raise YamlFileError(f"Entry '{key}' in '{key_path}' not found") from e

            except TypeError as e:
                raise YamlFileError(
                    f"'{prev_key}' in '{key_path}' is type: {type(curser)}",
                ) from e
            prev_key = key

        if type(curser) is scalarint.ScalarInt:
            curser = int(curser)
        return curser

    def remove_key(self, key_path: str):
        curser = self._yaml_data
        prev_key = ""
        keys = key_path.split(".")
        element = keys[-1]

        # Iterate through mappings to element
        for key in keys:
            if key == element:
                del curser[key]
                break
            try:
                curser = curser[key]
            except KeyError as e:
                raise YamlFileError(f"Entry '{key}' in '{key_path}' not found") from e
            except TypeError as e:
                raise YamlFileError(
                    f"'{prev_key}' in '{key_path}' is type: {type(curser)}",
                ) from e
            prev_key = key

        log.debug(f"Removed '{element}' from '{key_path}'")

    def set_key(
        self,
        key_path: str,
        value: YamlTypes,
    ):
        curser = self._yaml_data
        prev_key = ""
        keys = key_path.split(".")
        element = keys[-1]

        # Iterate through mappings to element
        for key in keys:
            if key == element:
                break  # Exit early to have pointer into parent structure

            try:
                if curser[key] is None:  # Handle empty keys as empty dicts
                    log.debug(f"Empty key '{element}' in '{key_path}'")
                    curser[key] = {element: None}
                curser = curser[key]
            except KeyError as e:
                raise YamlFileError(f"Entry '{key}' in '{key_path}' not found") from e
            except TypeError as e:
                raise YamlFileError(
                    f"'{prev_key}' in '{key_path}' is type: {type(curser)}",
                ) from e
            prev_key = key

        # Set element if exists or create it
        try:
            if curser[element]:  # Preserve type if existing
                curser[element] = type(curser[element])(value)
            else:
                curser[element] = value
        except KeyError:
            log.debug(f"Entry '{element}' in '{key_path}' not found - Creating")
            curser[element] = value

        log.debug(f"Set '{element}' in '{key_path}' to {value}")


def is_partial_match(query: str, target_list: list[str]) -> bool:
    for item in target_list:
        if query in item:
            return True
    return False
