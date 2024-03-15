"""
utility functions
"""

import contextlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

import edge_containers_cli.globals as globals
from edge_containers_cli.logging import log


def get_instance_image_name(svc_instance: Path, tag: Optional[str] = None) -> str:
    svc_instance = svc_instance.resolve()
    values = svc_instance / "values.yaml"
    if not values.exists():
        log.error(f"values.yaml not found in {svc_instance}")
        raise typer.Exit(1)

    values_text = values.read_text()
    matches = re.findall(r"image: (.*):(.*)", values_text)
    if len(matches) == 1:
        tag = tag or matches[0][1]
        image = matches[0][0] + f":{tag}"
    else:
        log.error(f"image tag definition not found in {values}")
        raise typer.Exit(1)

    return image


def check_instance_path(service_path: Path):
    """
    verify that the service instance path is valid
    """
    service_path = service_path.absolute()
    service_name = service_path.name.lower()

    log.info(f"checking instance {service_name} at {service_path}")
    if service_path.is_dir():
        if not (service_path / "values.yaml").exists():
            log.error("IOC instance requires values.yaml")
            raise typer.Exit(1)
    else:
        log.error(f"instance path {service_path} does not exist")
        raise typer.Exit(1)

    return service_name, service_path


def generic_ioc_from_image(image_name: str) -> str:
    """
    return the generic IOC name from an image name
    """
    match = re.findall(r".*\/(.*)-.*-(?:runtime|developer)", image_name)
    if not match:
        log.error(f"cannot extract generic IOC name from {image_name}")
        raise typer.Exit(1)

    return match[0]


def drop_path(raw_input: str):
    """
    Extracts the Service name if is a path through services
    """
    match = re.findall(
        r"services\/(.*?)(?:/|\s|$)", raw_input
    )  # https://regex101.com/r/L3GUvk/1
    if not match:
        return raw_input

    extracted_svc = match[0]
    typer.echo(f"Extracted service name {extracted_svc} from input: {raw_input}")

    return extracted_svc


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


def cleanup_temp(folder_path: Path) -> None:
    # keep the tmp folder if debug is enabled for inspection
    if not globals.EC_DEBUG:
        shutil.rmtree(folder_path, ignore_errors=True)
    else:
        log.debug(f"Temporary directory {folder_path} retained")


def normalize_tag(tag: str) -> str:
    """
    normalize a tag to be lowercase and replace any '/'
    this is needed in CI because dependabot tags
    """
    tag = tag.lower()
    tag = tag.replace("/", "-")
    return tag


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
