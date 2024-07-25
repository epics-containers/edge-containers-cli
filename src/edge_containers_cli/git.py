"""
Utility functions for working with git
"""

import os
from pathlib import Path

from edge_containers_cli.logging import log
from edge_containers_cli.shell import shell
from edge_containers_cli.utils import chdir


def create_version_map(repo: str, folder: Path) -> dict:
    """
    return a dictionary of the available IOCs (by discovering the children
    to the services/ folder in the beamline repo) as well as a list of the corresponding
    available versions for each IOC (by discovering the tags in the beamline repo at
    which changes to the instance were made since the last tag)
    """
    shell.run_command(f"git clone {repo} {folder}")
    path_list = os.listdir(os.path.join(folder, "services"))
    service_list = [
        path
        for path in path_list
        if os.path.isdir(os.path.join(folder, "services", path))
    ]
    log.debug(f"service_list = {service_list}")

    version_map: dict[str, list[str]] = {}

    with chdir(folder):  # From python 3.11 can use contextlib.chdir(folder)
        result_tags = str(
            shell.run_command("git tag --sort=committerdate")
        )
        tags_list = result_tags.rstrip().split("\n")
        log.debug(f"tags_list = {tags_list}")

        for tag_no, _ in enumerate(tags_list):
            # Check initial configuration
            if not tag_no:
                cmd = f"git ls-tree -r {tags_list[tag_no]} --name-only"
                changed_files = str(
                    shell.run_command(cmd, error_OK=True)
                )

            # Check repo changes between tags
            else:
                cmd = f"git diff --name-only {tags_list[tag_no-1]} {tags_list[tag_no]}"
                changed_files = str(
                    shell.run_command(cmd, error_OK=True)
                )

            # Test each service for changes
            for service_name in service_list:
                version_map[service_name] = []
                if service_name in changed_files:
                    version_map[service_name].append(tags_list[tag_no])
                elif "beamline_values.yaml" in changed_files:
                    version_map[service_name].append(tags_list[tag_no])

    return version_map
