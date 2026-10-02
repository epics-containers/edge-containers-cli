"""
Utility functions for working with git
"""

import os
import re
import shlex
from collections.abc import Mapping
from pathlib import Path

import polars
from natsort import natsorted
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError, shell
from edge_containers_cli.utils import (
    YamlFile,
    YamlFileError,
    YamlPathNotFoundError,
    YamlTypes,
    chdir,
    is_partial_match,
    new_workdir,
)


class GitError(Exception):
    pass


# an exact `X.Y.Z[-pre]` release version - a range/constraint (`^5.9.0`,
# `>=5.8.0`), a non-numeric scheme (`file://...`) or a git ref never
# matches, so it's treated as "can't prove it's new enough" by
# check_chart_dependency_version.
_RELEASE_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-.+)?$")


def _release_tuple(version: str) -> tuple[int, int, int] | None:
    """
    The (major, minor, patch) release segment of an exact semver string,
    ignoring any pre-release/build suffix, or None if `version` isn't a
    single exact version ec can compare.
    """
    match = _RELEASE_RE.match(version.strip())
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _read_dependency_version(chart_yaml: Path, dependency: str) -> str | None:
    """
    The version string pinned for `dependency` in `chart_yaml`'s
    `dependencies` list, or None if the file is missing/unreadable, isn't
    a Chart.yaml-shaped mapping, or has no entry named `dependency`.
    """
    try:
        with open(chart_yaml) as fp:
            chart = YAML(typ="safe").load(fp)
    except (OSError, YamlFileError):
        return None
    if not isinstance(chart, dict):
        return None
    for dep in chart.get("dependencies") or []:
        if isinstance(dep, dict) and dep.get("name") == dependency:
            version = dep.get("version")
            return str(version) if version is not None else None
    return None


def check_chart_dependency_version(
    chart_dir: Path,
    dependency: str,
    min_version: str,
    feature: str,
) -> None:
    """
    Raise GitError unless `chart_dir`/Chart.yaml pins `dependency` at or
    above `min_version`. Reads the Chart.yaml that already sits next to
    the values.yaml a caller is about to write - no extra clone.

    Fails closed: a missing Chart.yaml, a missing/unparsable `dependency`
    entry, or a version that isn't an exact `X.Y.Z[-pre]` (a range, a
    `file://` path, a git ref, ...) is treated as "can't prove it's new
    enough" and refused, not allowed through - there's no committed
    Chart.lock here to say what a range would actually resolve to. Only
    the release segment (major.minor.patch) is compared, so a pre-release
    of `min_version` itself (e.g. `5.10.0-rc1`) passes.
    """
    chart_yaml = chart_dir / "Chart.yaml"
    dep_version = _read_dependency_version(chart_yaml, dependency)
    dep_release = _release_tuple(dep_version) if dep_version is not None else None
    min_release = _release_tuple(min_version)
    assert min_release is not None, f"invalid min_version {min_version!r}"

    if dep_release is None or dep_release < min_release:
        raise GitError(
            f"'{feature}' needs the {dependency} chart at >= {min_version}, "
            f"but {chart_yaml} pins {dep_version or '(undetermined)'}. "
            f"Upgrade the {dependency} dependency in {chart_yaml} first - "
            "a version-only deploy (no description change) is unaffected."
        )


def resolve_target_revision(
    file_data: YamlFile,
    service_name: str,
    requested_version: str,
) -> str | None:
    """
    What `services.<service_name>.targetRevision` should become in the
    deployment repo's values file for a `deploy` to `requested_version`:
    `requested_version` itself if it differs from the shared revision
    line the service already follows, or None if it's the same - meaning
    the caller should remove any existing per-service pin instead of
    writing a redundant one.

    The line a service follows (ec-helm-charts#135's `argocd-apps`
    resolution order, minus the per-service override this call is about
    to decide the fate of): `versions[services.<service_name>.group]` if
    the service has a `group`, else the file's top-level
    `source.targetRevision`. A deployment repo with neither `versions`
    nor `group` (pre ec-helm-charts#135) falls straight through to that
    `source.targetRevision` comparison, unchanged from today.

    Raises GitError if the service has a non-empty `group` with no
    matching entry in `versions` - the chart render fails on that
    combination regardless (a typo must not be silently written over, or
    silently left as a dangling pin), so this refuses clearly rather
    than guessing.
    """
    try:
        group = file_data.get_key(f"services.{service_name}.group")
    except YamlFileError:
        group = None

    if group:
        try:
            line_revision = file_data.get_key(f"versions.{group}")
        except YamlFileError as e:
            raise GitError(
                f"service '{service_name}' has group '{group}' but "
                f"'versions.{group}' is not set in {file_data.file} - "
                "the chart render would fail on this; refusing to deploy"
            ) from e
    else:
        try:
            line_revision = file_data.get_key("source.targetRevision")
        except YamlFileError:
            # No top-level `source.targetRevision` at all - can't prove
            # the requested version is redundant, so always write it.
            line_revision = None

    return None if line_revision == requested_version else requested_version


def _dump(file_data: YamlFile, file: Path) -> None:
    """Write `file_data` back, as a GitError if the output doesn't parse."""
    try:
        file_data.dump_file()
    except YamlFileError as e:
        raise GitError(f"{e} - nothing was written to {file}") from e


def commit_args(generated: str, message: str | None) -> str:
    """
    Build the -m arguments for a commit.

    Without a note the generated summary is the whole message. With one the
    note becomes the subject, because that is what shows up in a log listing,
    and the generated summary is kept as the body so the machine-readable
    `Set ...` / `Remove ...` line stays greppable.
    """
    if message:
        return f"-m {shlex.quote(message)} -m {shlex.quote(generated)}"
    return f"-m {shlex.quote(generated)}"


async def set_value(
    repo_url: str,
    file: Path,
    key: str,
    value: YamlTypes,
    message: str | None = None,
) -> None:
    """
    sets a key,value pair in a yaml file and push the changes
    """
    with new_workdir() as path:
        try:
            await shell.run_command(f"git clone --depth=1 {repo_url} {path}")
            with chdir(path):  # From python 3.11 can use contextlib.chdir(working_dir)
                file_data = YamlFile(file)
                try:
                    value_repo = file_data.get_key(key)
                    if value_repo == value:
                        log.debug(f"{key} already set as {value}")
                        return None
                except YamlFileError:
                    pass

                try:
                    file_data.set_key(key, value)
                except YamlPathNotFoundError as e:
                    raise GitError(
                        f"'{key}' not found in {file} - nothing was written"
                    ) from e
                _dump(file_data, file)

                commit_msg = f"Set {key}={value} in {file}"
                await shell.run_command("git add .")
                await shell.run_command(
                    f"git commit {commit_args(commit_msg, message)}"
                )
                await shell.run_command("git push", skip_on_dryrun=True)

        except (FileNotFoundError, ShellError) as e:
            raise GitError(str(e)) from e


async def set_values(
    repo_url: str,
    file: Path,
    keys: dict[str, YamlTypes],
    require_keys: list[str] | None = None,
    require_chart_version: tuple[str, str, str] | None = None,
    deploy_target_revision: tuple[str, str] | None = None,
    remove_keys: list[str] | None = None,
    add_entry: str | None = None,
    message: str | None = None,
) -> None:
    """
    sets several key,value pairs in a yaml file in a single commit and
    pushes the changes. Any key not present in `keys` is left untouched -
    this lets a caller change only the fields it knows about without
    disturbing sibling fields (present or future) at the same parent.

    If a value is itself a dict and the key already holds a dict in the
    repo, the two are shallow-merged (the new value's keys win) rather
    than the existing dict being replaced outright - this lets a caller
    set one entry of e.g. a `labels` mapping without wiping any others.

    `require_keys`, if given, are key paths that must already exist in
    the file. If any is missing, nothing is written, committed or pushed
    and a GitError is raised instead - this stops a caller creating a new,
    partial entry (e.g. a lone `description` with no `enabled`/
    `targetRevision` siblings) for a service that was never deployed. A
    key that exists but holds YAML null (a bare `name:` entry, valid
    shorthand for "use every default") is treated as an empty mapping and
    created as one; a key holding a real scalar or a list is still
    rejected.

    `require_chart_version`, if given, is `(dependency, min_version,
    feature)`. Before any write, check_chart_dependency_version is run
    against the Chart.yaml beside `file` - if `dependency` isn't pinned to
    at least `min_version`, nothing is written, committed or pushed and a
    GitError is raised instead.

    `deploy_target_revision`, if given, is `(service_name,
    requested_version)`. `services.<service_name>.targetRevision` is
    resolved via resolve_target_revision against this same clone before
    anything is written: if `requested_version` is already the shared
    revision line the service follows, any existing per-service pin is
    removed instead of a redundant one being written; otherwise
    `requested_version` is set, exactly as though `keys` had carried
    `services.<service_name>.targetRevision: requested_version` directly.
    Raises GitError (nothing written) if the service's `group` has no
    matching entry in `versions` - see resolve_target_revision.

    `remove_keys`, if given, are key paths removed from the file instead
    of being set - a key already absent is not an error, there's simply
    nothing to do for it. This is how a caller drops e.g.
    `services.<service_name>.enabled` from the file entirely rather than
    writing an explicit `true`/`false` to it.

    `add_entry`, if given, is a key path (e.g. `services.<service_name>`)
    that is created as an empty mapping when the file has no entry there,
    or the entry it already has is YAML null (a bare `<service_name>:`,
    which Helm v4 drops as if the key were absent), before `keys`,
    `deploy_target_revision` and `remove_keys` are applied to it - this is
    how `ec deploy` adds a service the deployment repo does not list yet,
    or repairs one that is listed but null. An entry already present as
    anything other than null is left as it is. Its parent (e.g.
    `services`) must already exist, or GitError is raised with nothing
    written. Without `add_entry`, a missing entry is an error for every
    write, as above.
    """
    with new_workdir() as path:
        try:
            await shell.run_command(f"git clone --depth=1 {repo_url} {path}")
            with chdir(path):  # From python 3.11 can use contextlib.chdir(working_dir)
                file_data = YamlFile(file)

                if require_chart_version is not None:
                    check_chart_dependency_version(file.parent, *require_chart_version)

                for req_key in require_keys or []:
                    try:
                        req_value = file_data.get_key(req_key)
                    except YamlFileError as e:
                        raise GitError(
                            f"'{req_key}' not found in {file} - nothing was written"
                        ) from e
                    if req_value is None:
                        # A bare `name:` entry is valid YAML for "use every
                        # default" - it's an empty mapping, not an absent
                        # one, so create it rather than refusing a
                        # perfectly ordinary deployment. Real scalars
                        # (below) and lists are still rejected.
                        file_data.set_key(req_key, {})
                    elif not isinstance(req_value, Mapping):
                        raise GitError(
                            f"'{req_key}' in {file} is not a mapping "
                            f"(found {type(req_value).__name__}) - "
                            "nothing was written"
                        )

                added_entry = False
                repaired_null_entry = False
                if add_entry is not None:
                    try:
                        existing_entry = file_data.get_key(add_entry)
                        entry_present = True
                    except YamlFileError:
                        existing_entry = None
                        entry_present = False

                    # A bare `<service_name>:` entry (YAML null) is left
                    # as null by a write that only ever removes/replaces
                    # leaves below it (nothing to remove/replace under a
                    # null value), so without this it would survive a
                    # deploy untouched. Helm v4 drops a null-valued key
                    # as though it were absent, which would remove the
                    # service - treat it exactly like a missing entry.
                    if not entry_present or existing_entry is None:
                        try:
                            file_data.set_key(add_entry, CommentedMap())
                        except YamlPathNotFoundError as e:
                            raise GitError(
                                f"'{add_entry}' cannot be added to {file} - "
                                "nothing was written"
                            ) from e
                        if entry_present:
                            # It was already there, as null - this is a
                            # repair, not an addition, so the commit
                            # message below reads like any other value
                            # being set, not "Add ...".
                            repaired_null_entry = True
                        else:
                            added_entry = True

                remove_key_paths: list[str] = list(remove_keys or [])
                if deploy_target_revision is not None:
                    service_name, requested_version = deploy_target_revision
                    resolved = resolve_target_revision(
                        file_data, service_name, requested_version
                    )
                    target_revision_key = f"services.{service_name}.targetRevision"
                    if resolved is None:
                        remove_key_paths.append(target_revision_key)
                    else:
                        keys = {**keys, target_revision_key: resolved}

                changed: dict[str, YamlTypes] = {}
                for key, value in keys.items():
                    try:
                        value_repo = file_data.get_key(key)
                    except YamlFileError:
                        value_repo = None

                    if isinstance(value, dict) and isinstance(value_repo, dict):
                        merged = dict(value_repo)
                        merged.update(value)
                        value = merged

                    if value_repo == value:
                        log.debug(f"{key} already set as {value}")
                        continue

                    try:
                        file_data.set_key(key, value)
                    except YamlPathNotFoundError as e:
                        raise GitError(
                            f"'{key}' not found in {file} - nothing was written"
                        ) from e
                    changed[key] = value

                removed_keys: list[str] = []
                for remove_key_path in remove_key_paths:
                    try:
                        file_data.remove_key(remove_key_path)
                    except YamlPathNotFoundError as e:
                        # Unlike the leaf itself being absent (below), a
                        # missing intermediate segment means the thing
                        # being changed - e.g. the service itself - was
                        # never in the file at all. A mistyped or
                        # never-deployed service name must fail loudly,
                        # not be swallowed as a harmless no-op.
                        raise GitError(
                            f"'{remove_key_path}' not found in {file} - "
                            "nothing was written"
                        ) from e
                    except YamlFileError:
                        # Nothing to remove - already absent (e.g. the
                        # service already had no per-service targetRevision
                        # pin, so it was already following its line). Not
                        # an error, just nothing to do here.
                        pass
                    else:
                        removed_keys.append(remove_key_path)

                if (
                    not added_entry
                    and not repaired_null_entry
                    and not changed
                    and not removed_keys
                ):
                    return None

                if add_entry is not None and (added_entry or repaired_null_entry):
                    # The entry was just created (possibly still empty) -
                    # any comment that followed the previous last entry
                    # now sits on this entry's own slot
                    # (`_move_trailing_comment`); if nested keys were set
                    # above, sink it onto this entry's deepest last key so
                    # it still reads as following the entry's content.
                    file_data.sink_entry_comment(add_entry)

                _dump(file_data, file)

                parts = [f"{k}={v}" for k, v in changed.items()]
                parts.extend(f"remove {k}" for k in removed_keys)
                if repaired_null_entry:
                    # Reads like any other value being set (below), not
                    # like an addition - the entry already existed.
                    parts.insert(0, f"{add_entry}={{}}")
                if changed or repaired_null_entry:
                    summary = f"Set {', '.join(parts)}"
                elif removed_keys:
                    summary = f"Remove {', '.join(removed_keys)}"
                else:
                    summary = ""
                if added_entry:
                    summary = f"Add {add_entry}" + (
                        f", {summary[0].lower()}{summary[1:]}" if summary else ""
                    )
                commit_msg = f"{summary} in {file}"
                await shell.run_command("git add .")
                await shell.run_command(
                    f"git commit {commit_args(commit_msg, message)}"
                )
                await shell.run_command("git push", skip_on_dryrun=True)

        except (FileNotFoundError, ShellError) as e:
            raise GitError(str(e)) from e


async def del_key(
    repo_url: str, file: Path, key: str, message: str | None = None
) -> None:
    """
    remove a key from a yaml file and push the changes

    A key already absent from the file is not an error: nothing is
    committed and a note says so, so a caller can still do its follow-up
    steps (e.g. refresh the Argo CD app that renders the file). A missing
    intermediate segment means the file lacks the structure the key lives
    in, and raises GitError with nothing written.
    """
    with new_workdir() as path:
        try:
            await shell.run_command(f"git clone --depth=1 {repo_url} {path}")
            with chdir(path):  # From python 3.11 can use contextlib.chdir(working_dir)
                file_data = YamlFile(file)
                try:
                    file_data.remove_key(key)
                except YamlPathNotFoundError as e:
                    raise GitError(
                        f"'{key}' not found in {file} - nothing was written"
                    ) from e
                except YamlFileError:
                    log.warning(f"{key} already absent from {file} - no commit made")
                    return None
                _dump(file_data, file)

                commit_msg = f"Remove {key} in {file}"
                await shell.run_command("git add .")
                await shell.run_command(
                    f"git commit {commit_args(commit_msg, message)}"
                )
                await shell.run_command("git push", skip_on_dryrun=True)

        except (FileNotFoundError, ShellError) as e:
            raise GitError(str(e)) from e


async def _resolve_symlinks(
    symlink_object_map: dict[str, list[str]],
    file_list: list[str],
    cache: dict = {},  # noqa: B006
):
    """
    Propagate changes through symlink targets to source
    """
    ## Find symlink source mapping to git object
    if symlink_object_map:
        ## Find symlink mapping to target file
        symlink_map = {}  # source path: target path
        for symlink in symlink_object_map.keys():
            # If already retrieved git object, use stored
            if symlink_object_map[symlink] in cache:
                symlink_map[symlink] = cache[symlink_object_map[symlink]]
            # Else retrieve git object
            else:
                cmd = f"git cat-file -p {symlink_object_map[symlink]}"
                result_symlinks = str(await shell.run_command(cmd))
                symlink_map[symlink] = result_symlinks
                cache[symlink_object_map[symlink]] = result_symlinks

        ## Group sources per symlink target
        target_tree = {}
        for source, target_raw in symlink_map.items():
            target = str(
                os.path.normpath(  # Simplyfy path
                    os.path.join(
                        os.path.dirname(source), target_raw
                    ),  # resolve symlink
                )
            )
            target_tree.setdefault(target, []).append(source)
        log.debug(f"target_tree = {target_tree}")

        ## Include symlink source files as file changes
        for sym_target in target_tree.keys():
            if sym_target in file_list:
                file_list += target_tree[sym_target]


async def create_version_map(
    repo: str, root_dir: Path, working_dir: Path, shared_files: list[str] | None = None
) -> dict[str, list[str]]:
    """
    return a dictionary of each subdirectory in a chosen root directory in a git
    repository with a list of tags which represent changes. Symlinks are resolved.
    """
    await shell.run_command(f"git clone {repo} {working_dir}")
    try:
        os.listdir(os.path.join(working_dir, root_dir))
    except FileNotFoundError as e:
        raise GitError(f"No {root_dir} directory found") from e

    version_map = {}

    with chdir(working_dir):  # From python 3.11 can use contextlib.chdir(working_dir)
        result_tags = str(await shell.run_command("git tag --sort=committerdate"))
        if not result_tags:
            raise GitError("No tags found in repo")
        tags_list = result_tags.rstrip().split("\n")
        log.debug(f"tags_list = {tags_list}")

        cached_git_obj = {}  # Reduce making the same calls to git

        for tag_no, _ in enumerate(tags_list):
            # Check initial configuration
            if not tag_no:
                cmd = f"git ls-tree -r {tags_list[tag_no]} --name-only"
                changed_files = str(await shell.run_command(cmd)).split()

            # Check repo changes between tags
            else:
                cmd = (
                    f"git diff {tags_list[tag_no - 1]} {tags_list[tag_no]} --name-only"
                )
                changed_files = str(await shell.run_command(cmd)).split()

            cmd = f"git ls-tree -r {tags_list[tag_no]}"
            cmd_res = str(await shell.run_command(cmd, error_OK=True))
            symlink_object_map = {}
            service_list = []
            service_pattern = r"^services\/([^.].*)\/Chart\.yaml$"
            for entry in cmd_res.rstrip().split("\n"):
                line = entry.split()
                if line[0] == "120000":  # Check if is a symlink
                    symlink_object_map[entry.split()[-1]] = line[-2]
                if match := re.search(service_pattern, line[-1]):  # Check service
                    service_list.append(match.group(1))

            await _resolve_symlinks(symlink_object_map, changed_files, cached_git_obj)

            # Test against shared files
            if shared_files:
                shared_change_found = False
                for item in shared_files:
                    if item in changed_files:
                        for service_name in service_list:
                            version_map.setdefault(service_name, []).append(
                                tags_list[tag_no]
                            )
                            log.debug(
                                f"Added {tags_list[tag_no]} for {service_name} after shared file change"
                            )
                        shared_change_found = True
                        continue
                if shared_change_found:
                    continue

            # Test each service for changes
            for service_name in service_list:
                service_path = os.path.join(root_dir, service_name)
                if is_partial_match(service_path, changed_files):
                    version_map.setdefault(service_name, []).append(tags_list[tag_no])
                    log.debug(
                        f"Added {tags_list[tag_no]} for {service_name} after directory changes"
                    )
                    continue

    return version_map


async def list_all(
    repo: str, root_dir: Path, shared_files: list[str] | None = None
) -> polars.DataFrame:
    """List all services available in the service repository"""
    with new_workdir() as path:
        version_map = await create_version_map(
            repo, root_dir, path, shared_files=shared_files
        )
        svc_list = natsorted(version_map.keys())
        log.debug(f"version_map = {version_map}")

        versions = [natsorted(version_map[svc])[-1] for svc in svc_list]
        services_df = polars.from_dict({"name": svc_list, "version": versions})
        return services_df


async def list_instances(
    service_name: str, repo: str, root_dir: Path, shared_files: list[str] | None = None
) -> polars.DataFrame:
    with new_workdir() as path:
        version_map = await create_version_map(
            repo, root_dir, path, shared_files=shared_files
        )
        try:
            svc_list = version_map[service_name]
        except KeyError:
            svc_list = []

        sorted_list = natsorted(svc_list)[::-1]
        services_df = polars.from_dict({"version": sorted_list})
        return services_df


async def check_exists(path: Path, repo: str, tag: str) -> bool:
    """
    Check if a path exists within the given repository and tag/branch.
    """
    with new_workdir() as working_dir:
        try:
            await shell.run_command(f"git clone {repo} -b {tag} {working_dir}")
        except ShellError:
            log.debug(f"Branch or tag '{tag}' does not exist in repo '{repo}'.")
            return False
        full_path = Path(working_dir) / path
        if not full_path.exists():
            log.debug(f"'{path}' does not exist in repo '{repo}', tag {tag}.")
            return False
    return True
