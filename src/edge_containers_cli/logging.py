"""
Setup logging for the project
"""

import logging

from edge_containers_cli.definitions import ECLogLevels

log = logging.getLogger("edge-containers-cli")
handler = logging.StreamHandler()


def init_logging(level: ECLogLevels) -> None:
    log.setLevel(level.value)
    if log.level == logging.DEBUG:
        formatter = logging.Formatter(
            "%(levelname)s: %(pathname)s:%(lineno)d %(funcName)s \n\t%(message)s"
        )
    else:
        formatter = logging.Formatter("%(levelname)s:\t%(message)s")

    handler.setFormatter(formatter)
    log.addHandler(handler)

    log.debug("Debugging logging initialized")
