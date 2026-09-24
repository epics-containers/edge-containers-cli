"""
Tests for `-m/--message`, the note recorded on the git commit `ec` makes.

The option only means anything where ec commits, which is the Argo CD
backend. Everywhere else it must be absent from the CLI rather than
accepted and ignored - a note the user believes was recorded but was
not is worse than no option at all.
"""

import click
import pytest
import typer

from edge_containers_cli.cli import cli, drop_options
from edge_containers_cli.cmds.argo_commands import _require_commit_for_message
from edge_containers_cli.cmds.commands import CommandError
from edge_containers_cli.cmds.demo_commands import DemoCommands
from edge_containers_cli.cmds.k8s_commands import K8sCommands


def _params(command_name: str) -> list[str]:
    group = typer.main.get_command(cli)
    assert isinstance(group, click.Group)
    return [p.name for p in group.commands[command_name].params]


def test_message_is_offered_on_the_committing_commands():
    for command in ("delete", "deploy", "set-desc", "start", "stop"):
        assert "message" in _params(command), command


def test_k8s_backend_drops_message_everywhere_it_is_offered():
    # K8sCommands never commits, so every command that offers --message
    # must opt out of it.
    for command in ("delete", "deploy", "set-desc", "start", "stop"):
        assert "message" in K8sCommands.params_opt_out.get(command, []), command


def test_demo_backend_drops_message_from_the_commands_it_implements():
    # demo has no delete/deploy at all - those commands are removed by
    # drop_methods before drop_options runs, so opting out of them here
    # would be dead configuration.
    for command in ("set-desc", "start", "stop"):
        assert "message" in DemoCommands.params_opt_out.get(command, []), command
    assert "delete" not in DemoCommands.params_opt_out
    assert "deploy" not in DemoCommands.params_opt_out


def test_drop_options_removes_every_named_param():
    # Regression: the previous implementation popped from the list it was
    # enumerating, so the index shifted and the second of two params for
    # one command survived. K8sCommands drops both `commit` and `message`
    # from start/stop, which is exactly that case.
    group = typer.main.get_command(cli)
    ctx = click.Context(group)
    drop_options(ctx, {"start": ["commit", "message"]})
    names = [p.name for p in group.commands["start"].params]  # type: ignore[attr-defined]
    assert "commit" not in names
    assert "message" not in names
    assert "service_name" in names  # untouched


def test_drop_options_ignores_a_command_the_backend_does_not_have():
    # drop_methods runs first and removes unimplemented commands, so
    # drop_options must tolerate a name that is no longer registered
    # rather than raising KeyError.
    group = typer.main.get_command(cli)
    ctx = click.Context(group)
    drop_options(ctx, {"no-such-command": ["message"]})  # must not raise


def test_message_without_commit_is_refused():
    # start/stop without --commit patch the live Argo CD app and write
    # nothing to git, so there is no commit to carry the note.
    with pytest.raises(CommandError) as exc:
        _require_commit_for_message(commit=False, message="why I did this")
    assert "--commit" in str(exc.value)


def test_message_with_commit_is_allowed():
    _require_commit_for_message(commit=True, message="why I did this")


def test_no_message_needs_no_commit():
    _require_commit_for_message(commit=False, message=None)
