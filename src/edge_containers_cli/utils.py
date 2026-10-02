"""
utility functions
"""

import asyncio
import contextlib
import functools
import gc
import io
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any, Union

from ruamel.yaml import YAML, YAMLError, scalarint
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.scalarstring import ScalarString
from ruamel.yaml.tokens import CommentToken

import edge_containers_cli.globals as globals
from edge_containers_cli.logging import log

YamlPrimatives = Union[str, bool, int, None]
YamlTypes = Union[YamlPrimatives, dict[str, YamlPrimatives | dict[str, YamlPrimatives]]]

_AsyncFuncType = Callable[..., Coroutine[Any, Any, Any]]


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


class YamlPathNotFoundError(YamlFileError):
    """
    A key path can't be resolved at all because an intermediate segment
    (not the leaf itself) is missing - e.g. `services.<svc>.enabled` where
    `<svc>` has no entry under `services`. Distinct from the leaf itself
    being absent (plain YamlFileError), which a caller like
    `set_values(..., remove_keys=[...])` treats as "nothing to remove,
    already absent" - a missing intermediate means the thing being
    changed doesn't exist at all, which must never be swallowed as a
    harmless no-op.
    """


class YamlFile:
    def __init__(self, file: Path) -> None:
        self.file = file
        self._processor = YAML(typ="rt")  # 'rt' slower but preserves comments
        # Default width (80) wraps any line ec didn't touch that happens to
        # be longer, e.g. `source.repoURL: https://...` - a far wider line
        # width makes that wrap effectively never happen without changing
        # how short lines are emitted.
        self._processor.width = 4096
        # Keep a value's original quote style (e.g. `"main"`) on a rewrite
        # instead of dropping to plain style - ruamel only *adds* quotes
        # itself where a plain scalar would be misread (see set_key).
        self._processor.preserve_quotes = True
        with open(file) as fp:
            self._yaml_data = self._processor.load(fp)

    def dump_file(self, output_path: Path | None = None):
        """
        Write the data back out. The emitted YAML is parsed back first and
        nothing is written if it doesn't parse - a comment ruamel places
        badly must never reach the file.
        """
        output_path = output_path if output_path else self.file
        stream = io.BytesIO()
        self._processor.dump(self._yaml_data, stream)
        try:
            YAML(typ="safe").load(stream.getvalue())
        except YAMLError as e:
            raise YamlFileError(
                f"Refusing to write {output_path}: the YAML produced does not "
                f"parse ({e})"
            ) from e
        with open(output_path, "wb") as file_w:
            file_w.write(stream.getvalue())

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
        elif isinstance(curser, ScalarString):
            # preserve_quotes keeps quoted scalars as a ScalarString
            # subclass (for round-trip style) - callers compare/store this
            # as a plain string, same as get_key already normalises
            # ScalarInt to a plain int.
            curser = str(curser)
        return curser

    def remove_key(self, key_path: str):
        keys = key_path.split(".")
        element = keys[-1]
        parent: Any = None
        parent_key: Any = None
        curser = self._yaml_data
        prev_key = ""

        # Iterate through mappings to the one holding element
        for key in keys[:-1]:
            try:
                parent, parent_key, curser = curser, key, curser[key]
            except KeyError as e:
                raise YamlPathNotFoundError(
                    f"Entry '{key}' in '{key_path}' not found"
                ) from e
            except TypeError as e:
                raise YamlPathNotFoundError(
                    f"'{prev_key}' in '{key_path}' is type: {type(curser)}",
                ) from e
            prev_key = key

        try:
            curser[element]
        except KeyError as e:
            raise YamlFileError(f"Entry '{element}' in '{key_path}' not found") from e
        except TypeError as e:
            raise YamlFileError(
                f"'{prev_key}' in '{key_path}' is type: {type(curser)}",
            ) from e

        if isinstance(curser, CommentedMap):
            _remove_commented_key(curser, element, parent, parent_key)
        else:
            del curser[element]

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
                raise YamlPathNotFoundError(
                    f"Entry '{key}' in '{key_path}' not found"
                ) from e
            except TypeError as e:
                raise YamlPathNotFoundError(
                    f"'{prev_key}' in '{key_path}' is type: {type(curser)}",
                ) from e
            prev_key = key

        # Set element if exists or create it
        try:
            existing = curser[element]
        except KeyError:
            log.debug(f"Entry '{element}' in '{key_path}' not found - Creating")
            if isinstance(curser, CommentedMap):
                _move_trailing_comment(curser, element)
            curser[element] = value
        else:
            if existing and not isinstance(value, str):
                # Preserve the existing scalar's type/format (e.g. a
                # ruamel hex int or a yes/no-style bool) for a same-kind
                # value. A string value - every version/revision ec writes
                # is one - is set as a plain string instead: coercing it
                # through whatever type the existing scalar happened to be
                # can raise (`float("1.0.1")`) or silently change meaning.
                curser[element] = type(existing)(value)
            else:
                curser[element] = value

        log.debug(f"Set '{element}' in '{key_path}' to {value}")


# ruamel's round-trip loader keeps the comment lines that follow a value
# (an end-of-line comment plus any whole comment and blank lines up to the
# next key) on the deepest last key of that value, and the comment lines
# above a mapping's first key on the parent's entry for that mapping. The
# helpers below move those comments when a key is removed, so they stay
# where they were in the file instead of leaving with the key.

_EMPTY_COMMENT_SLOT = [None, None, None, None]


def _following_comment_slot(container: Any, key: Any) -> tuple[list, int]:
    """
    The `ca.items` entry, and the index in it, of the comment that follows
    `container[key]` - the deepest last key of a non-empty collection value.
    """
    value = container[key]
    if isinstance(value, CommentedMap) and len(value) > 0:
        return _following_comment_slot(value, list(value.keys())[-1])
    if isinstance(value, CommentedSeq) and len(value) > 0:
        return _following_comment_slot(value, len(value) - 1)
    slot = container.ca.items.setdefault(key, list(_EMPTY_COMMENT_SLOT))
    return slot, 0 if isinstance(container, CommentedSeq) else 2


def _append_following_comment(
    container: Any, key: Any, token: CommentToken, text: str
) -> None:
    """
    Add `text` (starting with the newline that ends `container[key]`'s
    last line) after `container[key]`'s existing following comment.
    """
    slot, index = _following_comment_slot(container, key)
    existing = slot[index]
    if existing is None:
        token.value = text
        slot[index] = token
    else:
        existing.value = existing.value + text[1:]


def _comment_lines_as_tokens(text: str) -> list[CommentToken]:
    """`text` (starting with a line-ending newline) as one token per line."""
    tokens = []
    for line in text[1:].splitlines(keepends=True):
        stripped = line.lstrip(" ")
        column = len(line) - len(stripped) if stripped.strip() else 0
        tokens.append(CommentToken(stripped, CommentMark(column), None))
    return tokens


def _remove_commented_key(
    mapping: CommentedMap, key: Any, parent: Any, parent_key: Any
) -> None:
    """
    Delete `mapping[key]`, keeping the comment and blank lines that follow
    it (they introduce whatever comes next). The removed line's own
    end-of-line comment goes with it. An emptied mapping is replaced by a
    fresh one: ruamel emits a leftover comment on an empty mapping at
    column 0, which does not parse.
    """
    keys = list(mapping.keys())
    position = keys.index(key)

    slot, index = _following_comment_slot(mapping, key)
    token = slot[index]
    slot[index] = None
    following = None
    if token is not None:
        text = token.value
        text = text[text.index("\n") :] if "\n" in text else ""
        if text not in ("", "\n"):
            following = text

    del mapping[key]
    mapping.ca.items.pop(key, None)

    if len(mapping) == 0 and parent is not None:
        parent[parent_key] = mapping = CommentedMap()

    if following is None or token is None:
        return

    if position > 0:
        _append_following_comment(mapping, keys[position - 1], token, following)
    elif len(mapping) == 0:
        if parent is not None:
            _append_following_comment(parent, parent_key, token, following)
    elif parent is not None:
        # nothing before it in this mapping: the comment now leads the
        # mapping's new first key
        slot = parent.ca.items.setdefault(parent_key, list(_EMPTY_COMMENT_SLOT))
        slot[3] = (slot[3] or []) + _comment_lines_as_tokens(following)
    else:
        mapping.ca.comment = mapping.ca.comment or [None, []]
        mapping.ca.comment[1] = (mapping.ca.comment[1] or []) + (
            _comment_lines_as_tokens(following)
        )


def _move_trailing_comment(mapping: CommentedMap, new_key: Any) -> None:
    """
    `mapping` is about to gain `new_key` as a brand-new entry, appended
    after its current last key. If that current last key has a comment
    following it (e.g. a section comment that actually precedes whatever
    comes after `mapping` itself - see `_following_comment_slot`), move it
    so it keeps following `mapping`'s content, i.e. after `new_key`, rather
    than being emitted between the old last key and `new_key` where it
    reads as if it were about the newly added entry.
    """
    keys = list(mapping.keys())
    if not keys:
        return

    slot, index = _following_comment_slot(mapping, keys[-1])
    token = slot[index]
    if token is None:
        return

    slot[index] = None
    new_slot = mapping.ca.items.setdefault(new_key, list(_EMPTY_COMMENT_SLOT))
    new_slot[2] = token


def is_partial_match(query: str, target_list: list[str]) -> bool:
    for item in target_list:
        if query in item:
            return True
    return False


def _run_async(coroutine: Coroutine):
    try:
        asyncio.get_running_loop()
        # We're in an async context — run in a separate thread with its own loop
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_run_on_new_loop, coroutine)
            ret = future.result()  # blocks the worker thread, not the event loop thread
    except RuntimeError:
        # No running loop — safe to block here
        ret = _run_on_new_loop(coroutine)

    return ret


def _run_on_new_loop(coroutine: Coroutine):
    """Run *coroutine* to completion on a fresh event loop, then tear the loop
    down cleanly.

    asyncio.Process / subprocess transports hold a reference cycle back to the
    loop, so their __del__ only fires during a GC pass. If that pass happens
    after the loop is closed (which is what asyncio.run() does on exit), the
    finalizer schedules a callback on the closed loop and asyncio prints
    "Event loop is closed" / "Loop ... that handles pid X is closed" spam.
    Forcing gc.collect() while the loop is still open lets those finalizers
    run against a live loop, so nothing fails.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.run_until_complete(loop.shutdown_asyncgens())
            gc.collect()
        finally:
            loop.close()


def async_command(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper
