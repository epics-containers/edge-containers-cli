from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

from edge_containers_cli.cmds.commands import CommandError
from edge_containers_cli.shell import shell
from edge_containers_cli.utils import (
    chdir,
    local_version,
    log,
    tmpdir,
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

        self.tmp = tmpdir.create()

    def __del__(self):
        if hasattr(self, "tmp"):
            tmpdir.cleanup()

    def cleanup_chart(self, service_path: Path):
        (service_path / "Chart.lock").unlink(missing_ok=True)
        for package in service_path.glob("*.tgz"):
            package.unlink(missing_ok=True)

    def deploy_local(self, service_path: Path):
        """
        Deploy a local helm chart directly to the cluster with dated beta version
        """

        validate_instance_path(service_path)
        self.cleanup_chart(service_path)
        self._do_deploy(service_path)

    def deploy(self):
        """
        Generate an IOC helm chart and deploy it to the cluster
        """
        if not self.version:
            raise CommandError("Version not found")

        shell.run_command(
            f"git clone {self.repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={self.version}",
        )

        self._do_deploy(self.tmp / "services" / self.service_name)

    def _do_deploy(self, service_folder: Path):
        """
        Generate an on the fly chart using beamline chart with config folder.
        Deploy the resulting helm chart to the cluster.
        """
        print(f"Deploying {self.service_name}:{self.version}")
        # package up the charts to get the appVersion set
        shell.run_command(f"helm dependency update {service_folder}")

        with chdir(service_folder):
            shell.run_command(
                f"helm package {service_folder} -u --app-version {self.version}",
            )

            # Determine package name
            with open("Chart.yaml") as fp:
                chart_yaml = YAML(typ="safe").load(fp)
            package_path = (
                service_folder / f'{chart_yaml["name"]}-{chart_yaml["version"]}.tgz'
            )

        # use helm to install the chart
        self._install(package_path)


    def _install(self, helm_chart: Path):
        """
        Execute helm install command
        """

        helm_cmd = "template" if self.template else "upgrade --install"
        cmd = (
            f"helm {helm_cmd} {self.service_name} {helm_chart} "
            f"--values {helm_chart.parent.parent}/beamline_values.yaml "  # Only if exists?
            f"--values {helm_chart.parent}/values.yaml "
            f"--namespace {self.namespace} "
            f"{self.args} "
        )
        shell.run_command(cmd, show=True, skip_on_dryrun=True)


def validate_instance_path(service_path: Path):
    """
    verify that the service instance path is valid
    """
    log.info(f"checking {service_path}")
    if not (service_path / "Chart.yaml").exists():
        raise CommandError("A service chart requires Chart.yaml")
    log.info("Chart.yaml found")
