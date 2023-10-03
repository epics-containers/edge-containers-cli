"""
Define a context for passing root parameters to sub-commands
"""

from dataclasses import dataclass


@dataclass
class Context:
    domain: str = ""
    beamline_repo: str = ""
    kubernetes_namespace: str = ""
