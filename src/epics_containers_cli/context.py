from dataclasses import dataclass


@dataclass
class Context:
    beamline: str = ""
    show_cmd: bool = False
