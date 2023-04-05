"""
Define a context for passing root parameters to sub-commands
"""

from dataclasses import dataclass


@dataclass
class Context:
    domain: str = ""
    helm_registry: str = ""
    show_cmd: bool = False
