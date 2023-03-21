"""
Setup logging for the project
"""
import logging

log = logging.getLogger("epics-containers-cli")
handler = logging.StreamHandler()


def init_logging(level: str):
    log.setLevel(level)
    if log.level == logging.DEBUG:
        formatter = logging.Formatter(
            "%(levelname)s: %(pathname)s:%(lineno)d %(funcName)s " "\n\t%(message)s"
        )
    else:
        formatter = logging.Formatter("%(levelname)s:\t%(message)s")

    handler.setFormatter(formatter)
    log.addHandler(handler)

    log.debug("Debugging logging initialized")
