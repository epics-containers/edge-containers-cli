from enum import Enum


class Architecture(str, Enum):
    linux = "linux"
    rtems = "rtems"
    arm = "arm"
