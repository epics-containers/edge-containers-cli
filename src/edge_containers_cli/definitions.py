from dataclasses import dataclass
from enum import Enum


class ECBackends(str, Enum):
    ARGOCD = "ARGOCD"
    K8S = "K8S"
    DEMO = "DEMO"


class ECLogLevels(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ENV(str, Enum):
    repo = "EC_SERVICES_REPO"
    target = "EC_TARGET"
    backend = "EC_CLI_BACKEND"
    verbose = "EC_VERBOSE"
    dryrun = "EC_DRYRUN"
    debug = "EC_DEBUG"
    log_level = "EC_LOG_LEVEL"
    log_url = "EC_LOG_URL"


@dataclass
class ECContext:
    repo: str = ""
    target: str = ""
    log_url: str = ""


class emoji(str, Enum):
    none = ""
    road_works = "\U0001f6a7"
    exclaim = "\U00002755"
    check_mark = "\U00002705"
    cross_mark = "\U0000274c"
    hour_glass = "\U000023f3c"
