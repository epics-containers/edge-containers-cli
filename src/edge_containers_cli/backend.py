"""
Manage a backend for the project
"""

from edge_containers_cli.cmds.argo_commands import ArgoCommands
from edge_containers_cli.cmds.commands import Commands
from edge_containers_cli.cmds.k8s_commands import K8sCommands
from edge_containers_cli.definitions import ECBackends, ECContext
from edge_containers_cli.utils import public_methods


class BackendError(Exception):
    pass


class Backend:
    def __init__(self) -> None:
        self._value: ECBackends | None = None
        self._cxt: ECContext | None = None
        self._Commands: type | None = None
        self._commands: Commands | None = None

    @property
    def commands(self):
        if self._commands is None:
            raise BackendError("Backend commands not constructed")
        else:
            return self._commands

    def set_backend(self, backend: ECBackends):
        self._value = backend
        if backend == ECBackends.K8S:
            self._Commands = K8sCommands
        elif backend == ECBackends.ARGOCD:
            self._Commands = ArgoCommands

    def check_deps(self):
        pass

    def set_context(self, context: ECContext):
        """
        Construct the appropriate Commands class
        """
        if self._Commands is None:
            pass
        else:
            self._cxt = context
            self._commands = self._Commands(context)

    def get_notimplemented(self) -> list[str]:
        notimplemented = []
        if self._Commands is None:
            return []
        else:
            for command in public_methods(self._Commands):
                if getattr(self._Commands, command) is getattr(Commands, command):
                    notimplemented.append(command)
        return notimplemented


backend = Backend()


def init_backend(set_backend: ECBackends):
    backend.set_backend(set_backend)
