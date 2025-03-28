"""
Utility functions for working with git
"""

import os
import re
from pathlib import Path

import polars
from natsort import natsorted

from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError, shell
from edge_containers_cli.utils import (
    YamlFile,
    YamlFileError,
    YamlTypes,
    chdir,
    is_partial_match,
    new_workdir,
)


class GitError(Exception):
    pass


def set_value(
    repo_url: str,
    file: Path,
    key: str,
    value: YamlTypes,
) -> None:
    """
    sets a key,value pair in a yaml file and push the changes
    """
    with new_workdir() as path:
        try:
            shell.run_command(f"git clone --depth=1 {repo_url} {path}")
            with chdir(path):  # From python 3.11 can use contextlib.chdir(working_dir)
                file_data = YamlFile(file)
                try:
                    value_repo = file_data.get_key(key)
                    if value_repo == value:
                        log.debug(f"{key} already set as {value}")
                        return None
                except YamlFileError:
                    pass

                file_data.set_key(key, value)
                file_data.dump_file()

                commit_msg = f"Set {key}={value} in {file}"
                shell.run_command("git add .")
                shell.run_command(f'git commit -m "{commit_msg}"')
                shell.run_command("git push", skip_on_dryrun=True)

        except (FileNotFoundError, ShellError) as e:
            raise GitError(str(e)) from e


def del_key(repo_url: str, file: Path, key: str) -> None:
    """
    remove a key from a yaml file and push the changes
    """
    with new_workdir() as path:
        try:
            shell.run_command(f"git clone --depth=1 {repo_url} {path}")
            with chdir(path):  # From python 3.11 can use contextlib.chdir(working_dir)
                file_data = YamlFile(file)
                file_data.remove_key(key)
                file_data.dump_file()

                commit_msg = f"Remove {key} in {file}"
                shell.run_command("git add .")
                shell.run_command(f'git commit -m "{commit_msg}"')
                shell.run_command("git push", skip_on_dryrun=True)

        except (FileNotFoundError, ShellError) as e:
            raise GitError(str(e)) from e


def _resolve_symlinks(
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
                result_symlinks = str(shell.run_command(cmd))
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


def create_version_map(
    repo: str, root_dir: Path, working_dir: Path, shared_files: list[str] | None = None
) -> dict[str, list[str]]:
    """
    return a dictionary of each subdirectory in a chosen root directory in a git
    repository with a list of tags which represent changes. Symlinks are resolved.
    """
    shell.run_command(f"git clone {repo} {working_dir}")
    try:
        os.listdir(os.path.join(working_dir, root_dir))
    except FileNotFoundError as e:
        raise GitError(f"No {root_dir} directory found") from e

    version_map = {}

    with chdir(working_dir):  # From python 3.11 can use contextlib.chdir(working_dir)
        result_tags = str(shell.run_command("git tag --sort=committerdate"))
        if not result_tags:
            raise GitError("No tags found in repo")
        tags_list = result_tags.rstrip().split("\n")
        log.debug(f"tags_list = {tags_list}")

        cached_git_obj = {}  # Reduce making the same calls to git

        for tag_no, _ in enumerate(tags_list):
            # Check initial configuration
            if not tag_no:
                cmd = f"git ls-tree -r {tags_list[tag_no]} --name-only"
                changed_files = shell.run_command(cmd).split()

            # Check repo changes between tags
            else:
                cmd = (
                    f"git diff {tags_list[tag_no - 1]} {tags_list[tag_no]} --name-only"
                )
                changed_files = shell.run_command(cmd).split()

            cmd = f"git ls-tree -r {tags_list[tag_no]}"
            cmd_res = str(shell.run_command(cmd, error_OK=True))
            symlink_object_map = {}
            service_list = []
            service_pattern = r"^services\/([^.].*)\/Chart\.yaml$"
            for entry in cmd_res.rstrip().split("\n"):
                line = entry.split()
                if line[0] == "120000":  # Check if is a symlink
                    symlink_object_map[entry.split()[-1]] = line[-2]
                if match := re.search(service_pattern, line[-1]):  # Check service
                    service_list.append(match.group(1))

            _resolve_symlinks(symlink_object_map, changed_files, cached_git_obj)

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


def list_all(
    repo: str, root_dir: Path, shared_files: list[str] | None = None
) -> polars.DataFrame:
    """List all services available in the service repository"""
    with new_workdir() as path:
        version_map = create_version_map(
            repo, root_dir, path, shared_files=shared_files
        )
        svc_list = natsorted(version_map.keys())
        log.debug(f"version_map = {version_map}")

        versions = [natsorted(version_map[svc])[-1] for svc in svc_list]
        services_df = polars.from_dict({"name": svc_list, "version": versions})
        return services_df


def list_instances(
    service_name: str, repo: str, root_dir: Path, shared_files: list[str] | None = None
) -> polars.DataFrame:
    with new_workdir() as path:
        version_map = create_version_map(
            repo, root_dir, path, shared_files=shared_files
        )
        try:
            svc_list = version_map[service_name]
        except KeyError:
            svc_list = []

        sorted_list = natsorted(svc_list)[::-1]
        services_df = polars.from_dict({"version": sorted_list})
        return services_df
