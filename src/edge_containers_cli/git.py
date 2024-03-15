"""
Utility functions for working with git
"""

import os
from pathlib import Path

import edge_containers_cli.shell as shell
from edge_containers_cli.logging import log
from edge_containers_cli.shell import check_services_repo
from edge_containers_cli.utils import chdir


def create_svc_graph(repo: str, folder: Path) -> dict:
    """
    return a dictionary of the available IOCs (by discovering the children
    to the services/ folder in the beamline repo) as well as a list of the corresponding
    available versions for each IOC (by discovering the tags in the beamline repo at
    which changes to the instance were made since the last tag) and the respective
    list of available versions
    """
    svc_graph = {}

    check_services_repo(repo)
    shell.run_command(f"git clone {repo} {folder}", interactive=False)
    path_list = os.listdir(os.path.join(folder, "services"))
    service_list = [
        path
        for path in path_list
        if os.path.isdir(os.path.join(folder, "services", path))
    ]
    log.debug(f"service_list = {service_list}")

    with chdir(folder):  # From python 3.11 can use contextlib.chdir(folder)
        for service_name in service_list:
            service_name = Path(service_name).name
            result = str(
                shell.run_command("git tag --sort=committerdate", interactive=False)
            )
            log.debug(f"checking these tags for changes in the instance: {result}")

            version_list = []
            tags = result.split("\n")
            tags.remove("")

            for tag_no, _ in enumerate(tags):
                # Check initial configuration
                if not tag_no:
                    cmd = f"git ls-tree -r {tags[tag_no]} --name-only"
                    result = str(
                        shell.run_command(cmd, interactive=False, error_OK=True)
                    )
                    if service_name in result:
                        version_list.append(tags[tag_no])

                # Check repo changes
                else:
                    cmd = f"git diff --name-only {tags[tag_no-1]} {tags[tag_no]}"
                    result = str(
                        shell.run_command(cmd, interactive=False, error_OK=True)
                    )
                    if service_name in result:
                        version_list.append(tags[tag_no])

            # Capture services committed since the most recent tag
            if not version_list:
                version_list.append("")

            svc_graph[service_name] = version_list

    return svc_graph
