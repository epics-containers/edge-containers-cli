"""
Setup logging for the project
"""
import logging

from epics_containers_cli.globals import EC_DEBUG

log = logging.getLogger("epics-containers-cli")
handler = logging.StreamHandler()


def init_logging(level: str, debug: bool = False):
    log.setLevel(level)
    if EC_DEBUG or debug:
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
