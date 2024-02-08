"""
utility functions
"""

import contextlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import typer

import ec_cli.globals as globals
from ec_cli.logging import log


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
            or not (ioc_path / globals.CONFIG_FOLDER).is_dir()
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


def drop_ioc_path(raw_input: str):
    """
    Extracts the IOC name if is a path through ioc
    """
    match = re.findall(
        r"iocs\/(.*?)(?:/|\s|$)", raw_input
    )  # https://regex101.com/r/L3GUvk/1
    if not match:
        return raw_input

    extracted_ioc = match[0]
    typer.echo(f"Extracted ioc name {extracted_ioc} from input: {raw_input}")

    return extracted_ioc


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


def json_to_table(json_data: str) -> Dict[str, List[str]]:
    """
    Convert a list of dictionaries in json into a dictionary of lists.
    This is to make it easy to juggle the columns of output from commands like
    helm list -o json.

    :param json_data: list of dictionaries
    :return: dictionary of lists with the keys being the column headers
    """
    try:
        data = json.loads(json_data)
        table = {}
        for row in data:
            for key, value in row.items():
                if key not in table:
                    table[key] = []
                table[key].append(value)
    except Exception as e:
        log.error(f"Error {e} parsing json: {json_data}")
        raise typer.Exit(1)
    return table


def csv_to_table(csv_data: str) -> Dict[str, List[str]]:
    """
    Convert a csv string into a dictionary of lists.

    :param csv_data: csv string
    :return: dictionary of lists with the keys being the column headers
    """
    try:
        lines = csv_data.splitlines()
        headings = lines[0].split(",")
        table = {heading: [] for heading in headings}
        for line in lines[1:]:
            values = line.split(",")
            for i, value in enumerate(values):
                table[headings[i]].append(value)
        return table
    except Exception as e:
        log.error(f"Error {e} parsing csv: {csv_data}")
        raise typer.Exit(1)


def make_table_str(
    data: Dict[str, List[str]], widths: Optional[List[int]] = None
) -> str:
    """
    Convert a dictionary into a column separated table

    :param data: dictionary to convert, keys are the column headers
                 values are arrays of the column values
    :param widths: optional dictionary of column widths, if not provided
                 the maximum width of each column will be used
    :return: a string with the table formatted using spaces and line feed
    """

    try:
        headings = list(data.keys())
        columns = len(headings)
        rows = len(data[headings[0]])
        if widths is None:
            # find the maximum width of each column from the data
            widths = [len(headings[i]) for i in range(columns)]
            for column in range(columns):
                for value in data[headings[column]]:
                    if len(str(value)) > widths[column]:
                        widths[column] = len(value)

        format_str = " ".join(
            [f"{{:<{widths[i]}.{widths[i]}}}" for i in range(columns)]
        )

        lines = format_str.format(*headings).upper()
        for row in range(rows):
            row_list = [data[headings[i]][row] for i in range(columns)]
            row_txt = format_str.format(*row_list)
            lines += "\n" + row_txt
    except Exception as e:
        log.error(f"Error {e} formatting table: {data}")
        raise typer.Exit(1)

    return lines
