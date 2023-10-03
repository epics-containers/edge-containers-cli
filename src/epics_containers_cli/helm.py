import subprocess
from pathlib import Path

import typer


def install(
    name: str,
    namespace: str,
    version: str,
    chart: Path,
    values: Path,
    dry_run: bool = False,
    debug: bool = False,
):
    """
    Execute helm install command
    """
    cmd = (
        f"helm upgrade --install {name} {chart} --version {version}"
        f" --namespace {namespace} -f {values}"
    )
    if dry_run:
        cmd += " --dry-run"
    if debug:
        cmd += " --debug"

    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        raise typer.Exit(1)
