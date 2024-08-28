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
