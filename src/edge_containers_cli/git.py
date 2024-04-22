"""
Utility functions for working with git
"""

import os
from pathlib import Path

import edge_containers_cli.shell as shell
from edge_containers_cli.logging import log
from edge_containers_cli.shell import check_services_repo
from edge_containers_cli.utils import chdir


def create_version_map(repo: str, folder: Path) -> dict:
    """
    return a dictionary of the available IOCs (by discovering the children
    to the services/ folder in the beamline repo) as well as a list of the corresponding
    available versions for each IOC (by discovering the tags in the beamline repo at
    which changes to the instance were made since the last tag) and the respective
    list of available versions
    """
    check_services_repo(repo)
    shell.run_command(f"git clone {repo} {folder}", interactive=False)
    path_list = os.listdir(os.path.join(folder, "services"))
    service_list = [
        path
        for path in path_list
        if os.path.isdir(os.path.join(folder, "services", path))
    ]
    log.debug(f"service_list = {service_list}")

    version_map = {service_item: [] for service_item in service_list}

    with chdir(folder):  # From python 3.11 can use contextlib.chdir(folder)
        result_tags = str(
            shell.run_command("git tag --sort=committerdate", interactive=False)
        )
        tags_list = result_tags.rstrip().split("\n")
        log.debug(f"tags_list = {tags_list}")

        cached_git_obj = {}  # Reduce making the same calls to git

        for tag_no, _ in enumerate(tags_list):
            # Check initial configuration
            if not tag_no:
                cmd = f"git ls-tree -r {tags_list[tag_no]} --name-only"
                changed_files = str(
                    shell.run_command(cmd, interactive=False, error_OK=True)
                )

            # Check repo changes between tags
            else:
                cmd = f"git diff --name-only {tags_list[tag_no-1]} {tags_list[tag_no]}"
                changed_files = str(
                    shell.run_command(cmd, interactive=False, error_OK=True)
                )

                # Propagate changes through symlink target to source
                ## Find symlink source mapping to git object
                cmd = f"git ls-tree {tags_list[tag_no]} -r | grep 120000"
                result_symlink_obj = str(
                    shell.run_command(cmd, interactive=False, error_OK=True)
                )
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
                            result_symlinks = str(
                                shell.run_command(cmd, interactive=False, error_OK=True)
                            )
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
                if service_name in changed_files:
                    version_map[service_name].append(tags_list[tag_no])

    return version_map
