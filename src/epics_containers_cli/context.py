"""
Define a context for passing root parameters to sub-commands
"""

from dataclasses import dataclass


@dataclass
class Context:
    domain: str = ""
    kubernetes_namespace: str = ""
    beamline_repo: str = ""
    beamline_org: str = ""
