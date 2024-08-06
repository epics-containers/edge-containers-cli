"""
Utility functions for working with git
"""

import os
from pathlib import Path

import polars
from natsort import natsorted

from edge_containers_cli.logging import log
from edge_containers_cli.shell import shell
from edge_containers_cli.utils import chdir, new_workdir


class GitError(Exception):
    pass


def create_version_map(
    repo: str, root_dir: Path, working_dir: Path, shared: str = None
) -> dict[str : list[str]]:
    """
    return a dictionary of each subdirectory in a chosen root directory in a git
    repository with a list of tags which represent changes. Symlinks are resolved.
    """
    shell.run_command(f"git clone {repo} {working_dir}")
    try:
        path_list = os.listdir(os.path.join(working_dir, root_dir))
    except FileNotFoundError:
        raise GitError(f"No {root_dir} directory found")
    service_list = [
        path
        for path in path_list
        if os.path.isdir(os.path.join(working_dir, root_dir, path))
    ]
    shared_path = os.path.join(working_dir, root_dir, shared)
    log.debug(f"service_list = {service_list}")

    version_map = {service_item: [] for service_item in service_list}

    with chdir(working_dir):  # From python 3.11 can use contextlib.chdir(working_dir)
        result_tags = str(shell.run_command("git tag --sort=committerdate"))
        if not result_tags:
            raise GitError(f"No tags found in repo")
        tags_list = result_tags.rstrip().split("\n")
        log.debug(f"tags_list = {tags_list}")

        cached_git_obj = {}  # Reduce making the same calls to git

        for tag_no, _ in enumerate(tags_list):
            # Check initial configuration
            if not tag_no:
                cmd = f"git ls-tree -r {tags_list[tag_no]} --name-only"
                changed_files = str(shell.run_command(cmd))

            # Check repo changes between tags
            else:
                cmd = f"git diff --name-only {tags_list[tag_no-1]} {tags_list[tag_no]}"
                changed_files = str(shell.run_command(cmd))

                # Propagate changes through symlink target to source
                ## Find symlink source mapping to git object
                cmd = f"git ls-tree {tags_list[tag_no]} -r | grep 120000"
                result_symlink_obj = str(shell.run_command(cmd, error_OK=True))
                if not result_symlink_obj:
                    pass
                else:
                    symlink_object_map = {  # source path: git object
                        entry.split()[-1]: entry.split()[-2]
                        for entry in result_symlink_obj.rstrip().split("\n")
                    }

                    ## Find symlink mapping to target file
                    symlink_map = {}  # source path: target path
                    for symlink in symlink_object_map.keys():
                        # If already retrieved git object, use stored
                        if symlink_object_map[symlink] in cached_git_obj:
                            symlink_map[symlink] = cached_git_obj[
                                symlink_object_map[symlink]
                            ]
                        # Else retrieve git object
                        else:
                            cmd = f"git cat-file -p {symlink_object_map[symlink]}"
                            result_symlinks = str(shell.run_command(cmd))
                            symlink_map[symlink] = result_symlinks
                            cached_git_obj[symlink_object_map[symlink]] = (
                                result_symlinks
                            )

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
                        if sym_target in changed_files:
                            changed_files = "\n".join(
                                [changed_files, *target_tree[sym_target]]
                            )

            # Test each service for changes
            for service_name in service_list:
                if shared_path in changed_files:
                    version_map[service_name].append(tags_list[tag_no])
                elif os.path.join(root_dir, service_name) in changed_files:
                    version_map[service_name].append(tags_list[tag_no])

    return version_map


def list_all(repo: str, root_dir: Path, shared: str = None) -> polars.DataFrame:
    """List all services available in the service repository"""
    with new_workdir() as path:
        version_map = create_version_map(repo, root_dir, path, shared=shared)
        svc_list = natsorted(version_map.keys())
        log.debug(f"version_map = {version_map}")

        versions = [natsorted(version_map[svc])[-1] for svc in svc_list]
        services_df = polars.from_dict({"name": svc_list, "version": versions})
        return services_df


def list_instances(
    service_name: str, repo: str, root_dir: Path, shared: str = None
) -> polars.DataFrame:
    with new_workdir() as path:
        version_map = create_version_map(repo, root_dir, path, shared)
        try:
            svc_list = version_map[service_name]
        except KeyError:
            svc_list = []

        sorted_list = natsorted(svc_list)[::-1]
        services_df = polars.from_dict({"version": sorted_list})
        return services_df
