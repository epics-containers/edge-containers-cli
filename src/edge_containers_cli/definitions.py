from dataclasses import dataclass
from enum import Enum


class ECBackends(str, Enum):
    ARGOCD = "ARGOCD"
    K8S = "K8S"


class ECLogLevels(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ENV(str, Enum):
    repo = "EC_SERVICES_REPO"
    namespace = "EC_NAMESPACE"
    backend = "EC_CLI_BACKEND"
    verbose = "EC_VERBOSE"
    debug = "EC_DEBUG"
    log_level = "EC_LOG_LEVEL"
    log_url = "EC_LOG_URL"


@dataclass
class ECContext:
    repo: str = ""
    namespace: str = ""
    log_url: str = ""
