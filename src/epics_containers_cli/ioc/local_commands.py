"""
Implements functions for deploying and managing local ioc instances using
local docker standalone. This is an initial experimental implementation.
In future we could support remote deployment and possibly creating
portainer manifests.

However, for the moment, Using this by connecting to each server and running
'ec deploy <ioc_name> <ioc_version> and then managing the network with a
tool like Portainer is a decent workflow.
"""
import re
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import requests
import typer

import epics_containers_cli.globals as glob_vars
from epics_containers_cli.docker import Docker
from epics_containers_cli.globals import (
    CONFIG_FILE_GLOB,
    CONFIG_FOLDER,
    IOC_CONFIG_FOLDER,
    LOCAL_NAMESPACE,
    Context,
)
from epics_containers_cli.ioc.k8s_commands import check_namespace
from epics_containers_cli.logging import log
from epics_containers_cli.shell import check_beamline_repo, run_command
from epics_containers_cli.utils import (
    check_ioc_instance_path,
    generic_ioc_from_image,
    get_instance_image_name,
)


class IocLocalCommands:
    """
    A class for implementing the ioc command namespace for local docker/podman
    """

    def __init__(
        self, ctx: Optional[Context], ioc_name: str = "", with_docker: bool = True
    ):
        self.namespace = ""
        self.beamline_repo: str = ""
        if ctx is not None:
            self.beamline_repo = ctx.beamline_repo
            self.namespace = ctx.namespace

        self.ioc_name: str = ioc_name

        self.tmp = Path(mkdtemp())
        self.ioc_folder = self.tmp / "iocs" / ioc_name
        self.docker = Docker(check=with_docker)

    def __del__(self):
        # keep the tmp folder if debug is enabled for inspection_del
        if not glob_vars.EC_DEBUG:
            if hasattr(self, "tmp"):
                shutil.rmtree(self.tmp, ignore_errors=True)

    def attach(self):
        self.docker.attach(self.ioc_name)

    def delete(self):
        if not typer.confirm(
            f"This will remove the IOC container {self.ioc_name} "
            "from the this server. Are you sure ?"
        ):
            raise typer.Abort()
        self.docker.remove(self.ioc_name)

    def _do_deploy(self, ioc_instance: Path, version: str, args: str):
        ioc_name, ioc_path = check_ioc_instance_path(ioc_instance)

        image = get_instance_image_name(ioc_instance)
        log.debug(f"deploying {ioc_instance} with image {image}")
        config = ioc_instance / CONFIG_FOLDER
        ioc_name = ioc_instance.name
        volume = f"{ioc_name}_config"

        self.docker.remove(ioc_name)
        run_command(f"{self.docker.docker} volume rm -f {volume}", interactive=False)
        run_command(f"{self.docker.docker} volume create {volume}", interactive=False)

        vol = f"-v {volume}:{IOC_CONFIG_FOLDER}"
        label = f"-l is_IOC=true -l version={version}"
        cmd = f"run -dit --net host --restart unless-stopped {label} {vol} {args}"
        dest = "busybox:copyto"

        # get the config into the volume before launching the IOC container
        run_command(f"{self.docker.docker} rm -f busybox", interactive=False)
        run_command(
            f"{self.docker.docker} container create --name busybox "
            f"-v {volume}:/copyto busybox",
            interactive=False,
        )
        for file in config.glob("*"):
            run_command(f"{self.docker.docker} cp {file} {dest}", interactive=False)
        run_command(f"{self.docker.docker} rm -f busybox", interactive=False)

        # launch the ioc container with mounted config volume
        run_command(f"{self.docker.docker} {cmd} --name {ioc_name} {image}")
        if not self.docker.is_running(ioc_name, retry=5):
            typer.echo(
                f"Failed to start {ioc_name} please try 'ec ioc logs {ioc_name}'"
            )
            raise typer.Exit(1)

    def deploy_local(self, ioc_instance: Path, yes: bool, args: str):
        """
        Use a local copy of an ioc instance definition to deploy a temporary
        version of the IOC to the local docker instance
        """
        version = datetime.strftime(datetime.now(), "%Y.%-m.%-d-b%-H.%-M")
        if not yes:
            typer.echo(
                f"Deploy TEMPORARY version {version} "
                f"from {ioc_instance} to the local docker instance"
            )
            if not typer.confirm("Are you sure ?"):
                raise typer.Abort()
        self._do_deploy(ioc_instance, version, args)

    def deploy(self, ioc_name: str, version: str, args: str):
        """
        deploy a tagged version of an ioc from a remote repo
        """

        check_beamline_repo(self.beamline_repo)

        run_command(
            f"git clone {self.beamline_repo} {self.tmp} --depth=1 "
            f"--single-branch --branch={version}",
            interactive=False,
        )

        self._do_deploy(self.ioc_folder, version, args)

    def exec(self):
        self.docker.exec(self.ioc_name, "bash", args="-it")

    def logs(self, prev: bool, follow: bool):
        self.docker.logs(self.ioc_name, prev, follow)

    def restart(self):
        run_command(f"{self.docker.docker} restart {self.ioc_name}")

    def start(self):
        run_command(f"{self.docker.docker} start {self.ioc_name}")

    def stop(self):
        run_command(f"{self.docker.docker} stop {self.ioc_name}")

    def ps(self, all: bool, wide: bool):
        all_arg = " --all" if all else ""

        # We have to build the table ourselves because docker is unable to
        # format a table with labels.
        format = "{{.Names}}%{{.Labels}}%{{.Status}}%{{.Image}}"

        result = run_command(
            f"{self.docker.docker} ps{all_arg} --filter label=is_IOC=true "
            f'--format "{format}"',
            interactive=False,
        )
        # this regex extracts just the version from the set of all labels
        result = re.sub(r"%.*?[,%]version=([^,%]*).*?%", r"%\1%", str(result))

        lines = ["IOC NAME%VERSION%STATUS%IMAGE"]
        lines += str(result).splitlines()
        rows = []
        for line in lines:
            rows.append(line.split("%"))

        for row in rows:
            print("{0: <20.20} {1: <20.20} {2: <23.23} {3}".format(*row))

    def validate_instance(self, ioc_instance: Path):
        check_ioc_instance_path(ioc_instance)

        typer.echo(f"Validating {ioc_instance}")

        ioc_config_files = list(
            ioc_instance.glob(str(Path(CONFIG_FOLDER) / CONFIG_FILE_GLOB))
        )
        image = get_instance_image_name(ioc_instance)
        image_name, image_tag = image.split(":")

        tmp = Path(mkdtemp())
        schema_file = tmp / "schema.json"

        # not all IOCs have a config file so no config validation for them
        if len(ioc_config_files) != 1:
            log.warning(f"No ioc config file found in {ioc_instance}, skipping.")
        else:
            ioc_config_file = ioc_config_files[0]
            config = ioc_config_file.read_text()
            matches = re.findall(r"#.* \$schema=(.*)", config)
            if not matches:
                raise RuntimeError("No schema modeline found in {ioc_config_file}")

            schema_url = matches[0]

            log.info(f"Downloading schema file {schema_url} to {schema_file}")
            with requests.get(schema_url, allow_redirects=True) as r:
                schema_file.write_text(r.content.decode())

            self.docker.run_tool(
                image="ghcr.io/epics-containers/yajsv",
                args=f"-s {schema_file} {ioc_config_file}",
            )

            # check that the image name and the schema are from the same generic IOC
            if image_tag not in schema_url:
                log.error(f"image version {image_tag} and {schema_url} do not match")
                raise typer.Exit(1)

            # make sure that generic IOC name matches the schema
            generic_ioc = generic_ioc_from_image(image_name)
            if generic_ioc not in schema_url:
                log.error(
                    f"ioc.yaml schema {schema_url} does not match generic IOC {generic_ioc}"
                )
                raise typer.Exit(1)

        # verify that the values.yaml file points to a container image that exists
        run_command(f"{self.docker.docker} manifest inspect {image}", interactive=False)

        shutil.rmtree(tmp, ignore_errors=True)

        typer.echo(f"{ioc_instance} validated successfully")

    def environment(self, verbose: bool):
        """
        declare the environment settings for ec
        """
        ns = self.namespace

        if ns == LOCAL_NAMESPACE:
            typer.echo("ioc commands deploy to the local docker/podman instance")
        else:
            check_namespace(ns)
            typer.echo(f"ioc commands deploy to the {ns} namespace the K8S cluster")

        typer.echo("\nEC environment variables:")
        run_command("env | grep '^EC_'", interactive=False, show=True)
