"""
Setup logging for the project
"""

import logging

import edge_containers_cli.globals as globals

log = logging.getLogger("edge-containers-cli")
handler = logging.StreamHandler()


def init_logging(level: str):
    log.setLevel(level)
    if globals.EC_DEBUG:
        log.setLevel(logging.DEBUG)
    if log.level == logging.DEBUG:
        formatter = logging.Formatter(
            "%(levelname)s: %(pathname)s:%(lineno)d %(funcName)s " "\n\t%(message)s"
        )
    else:
        formatter = logging.Formatter("%(levelname)s:\t%(message)s")

    handler.setFormatter(formatter)
    log.addHandler(handler)

    log.debug("Debugging logging initialized")
