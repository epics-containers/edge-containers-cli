from collections.abc import Callable
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

import edge_containers_cli.globals as globals
from edge_containers_cli.cmds.commands import CommandError
from edge_containers_cli.shell import shell
from edge_containers_cli.utils import (
    chdir,
    local_version,
    log,
    new_workdir,
)


class Helm:
    """
    A class for handling helm operations
    """

    def __init__(
        self,
        namespace: str,
        service_name: str,
        args: str = "",
        version: Optional[str] = None,
        template: bool = False,
        repo: Optional[str] = None,
    ):
        """
        Create a helm chart from a local or a remote repo
        """
        self.service_name = service_name
        self.repo = repo
        self.namespace = namespace
        self.args = args
        self.version = version or local_version()
        self.template = template

        self._work_dir = new_workdir()
        self.tmp = self._work_dir.create()

    def __del__(self):
        if hasattr(self, "tmp"):
            self._work_dir.cleanup()

    def cleanup_chart(self, service_path: Path):
        (service_path / "Chart.lock").unlink(missing_ok=True)
        for package in service_path.glob("*.tgz"):
            package.unlink(missing_ok=True)

    def deploy_local(
        self, service_path: Path, confirm_callback: Callable[[str], None] | None = None
    ):
        """
        Deploy a local helm chart directly to the cluster with dated beta version
        """

        if confirm_callback:
            confirm_callback(self.version)
        validate_instance_path(service_path)
        self.cleanup_chart(service_path)
        self._do_deploy(service_path)

    def deploy(self, confirm_callback: Callable[[str], None] | None = None):
        """
        Clone a helm chart and deploy it to the cluster
        """
        if confirm_callback:
            confirm_callback(self.version)
        shell.run_command(
            f"git clone {self.repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={self.version}",
        )
        self._do_deploy(self.tmp / "services" / self.service_name)

    def _do_deploy(self, service_folder: Path):
        """
        Package a Helm chart and deploy it to the cluster
        """

        action = "Templating" if self.template else "Deploying"
        print(f"{action} {self.service_name}:{self.version}")

        # package up the charts to get the appVersion set
        with chdir(service_folder):
            shell.run_command(
                f"helm package {service_folder} -u --app-version {self.version}",
            )

            # Determine package name
            with open("Chart.yaml") as fp:
                chart_yaml = YAML(typ="safe").load(fp)
            package_path = (
                service_folder / f"{chart_yaml['name']}-{chart_yaml['version']}.tgz"
            )

        # use helm to install the chart
        self._install(package_path)

    def _install(self, helm_chart: Path):
        """
        Execute helm install command
        """

        shared_vals = ""
        if (helm_chart.parent.parent.parent / globals.SHARED_VALUES).exists():
            shared_vals = f"--values {helm_chart.parent.parent}/values.yaml "

        helm_cmd = "template" if self.template else "upgrade --install"
        namespace = f"--namespace {self.namespace} " if self.namespace else ""
        cmd = (
            f"helm {helm_cmd} {self.service_name} {helm_chart} "
            f"{shared_vals} "
            f"--values {helm_chart.parent}/values.yaml "
            f"{namespace} "
            f"{self.args} "
        )
        shell.run_command(cmd, show=True, skip_on_dryrun=True)


def validate_instance_path(service_path: Path):
    """
    verify that the chart path is valid
    """
    log.info(f"checking {service_path}")
    if not (service_path / "Chart.yaml").exists():
        raise CommandError("A service chart requires Chart.yaml")
    log.info("Chart.yaml found")
