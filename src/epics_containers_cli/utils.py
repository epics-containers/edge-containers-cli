"""
utility functions
"""

import re
from pathlib import Path
from typing import Optional

import typer

from epics_containers_cli.logging import log

from .globals import CONFIG_FOLDER


def get_instance_image_name(ioc_instance: Path, tag: Optional[str] = None) -> str:
    ioc_instance = ioc_instance.resolve()
    values = ioc_instance / "values.yaml"
    if not values.exists():
        log.error(f"values.yaml not found in {ioc_instance}")
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


def check_ioc_instance_path(ioc_path: Path):
    """
    verify that the ioc instance path is valid
    """
    ioc_path = ioc_path.absolute()
    ioc_name = ioc_path.name.lower()

    log.info(f"checking IOC instance {ioc_name} at {ioc_path}")
    if ioc_path.is_dir():
        if (
            not (ioc_path / "values.yaml").exists()
            or not (ioc_path / CONFIG_FOLDER).is_dir()
        ):
            log.error("IOC instance requires values.yaml and config")
            raise typer.Exit(1)
    else:
        log.error(f"IOC instance path {ioc_path} does not exist")
        raise typer.Exit(1)

    return ioc_name, ioc_path


def generic_ioc_from_image(image_name: str) -> str:
    """
    return the generic IOC name from an image name
    """
    match = re.findall(r".*\/(.*)-.*-(?:runtime|developer)", image_name)
    if not match:
        log.error(f"cannot extract generic IOC name from {image_name}")
        raise typer.Exit(1)

    return match[0]
