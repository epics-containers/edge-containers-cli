import pytest

from edge_containers_cli.cmds.commands import CommandError
from edge_containers_cli.cmds.demo_commands import DemoCommands
from edge_containers_cli.definitions import ECContext


def test_logs(mock_run, DEMO):
    mock_run.run_cli("logs demo-ea-01")


def test_log_history(mock_run, DEMO):
    mock_run.run_cli("log-history demo-ea-01")


def test_restart(mock_run, DEMO):
    mock_run.run_cli("restart demo-ea-01")


def test_start(mock_run, DEMO):
    mock_run.run_cli("start demo-ea-01")


def test_stop(mock_run, DEMO):
    mock_run.run_cli("stop demo-ea-01")


def test_set_desc(mock_run, DEMO):
    # `Commands.set_description` is now abstract - DemoCommands must
    # implement it (a real decision, e.g. a CommandError like the
    # plain-k8s backend, or a validate-and-no-op like this) rather than
    # silently inheriting the base's `raise NotImplementedError`.
    mock_run.run_cli("set-desc demo-ea-01 new-description")


def test_set_desc_unknown_service(mock_run, DEMO):
    with pytest.raises(CommandError, match="not found"):
        mock_run.run_cli("set-desc no-such-service new-description")


def test_ps(mock_run, DEMO, wide_console):
    expect = (
        "╭────────────┬────────────────┬─────────┬────────┬─────────┬──────────────────────╮\n"
        "│ name       │ description    │ health  │ sync   │ version │ last sync            │\n"
        "├────────────┼────────────────┼─────────┼────────┼─────────┼──────────────────────┤\n"
        "│ demo-ea-00 │ demo-device-00 │ Healthy │ Synced │ 1.0.25  │ 2024-10-22T11:23:08Z │\n"
        "│ demo-ea-01 │ demo-device-01 │ Healthy │ Synced │ 1.0.24  │ 2024-10-22T11:23:03Z │\n"
        "│ demo-ea-02 │ demo-device-02 │ Healthy │ Synced │ 1.0.23  │ 2024-10-22T11:23:04Z │\n"
        "│ demo-ea-03 │ demo-device-03 │ Healthy │ Synced │ 1.0.22  │ 2024-10-22T11:23:07Z │\n"
        "│ demo-ea-04 │ demo-device-04 │ Healthy │ Synced │ 1.0.21  │ 2024-10-22T11:23:01Z │\n"
        "│ demo-ea-05 │ demo-device-05 │ Healthy │ Synced │ 1.0.20  │ 2024-10-22T11:23:03Z │\n"
        "│ demo-ea-06 │ demo-device-06 │ Healthy │ Synced │ 1.0.19  │ 2024-10-22T11:23:07Z │\n"
        "│ demo-ea-07 │ demo-device-07 │ Healthy │ Synced │ 1.0.18  │ 2024-10-22T11:23:01Z │\n"
        "╰────────────┴────────────────┴─────────┴────────┴─────────┴──────────────────────╯\n"
    )

    res = mock_run.run_cli("ps")

    assert expect in res


def test_unset_repo_reports_cleanly():
    # DemoCommands must chain to the base constructor - otherwise _repo /
    # _log_url do not exist and the friendly "Please set ..." message
    # becomes an AttributeError traceback.
    commands = DemoCommands(ECContext())

    with pytest.raises(CommandError, match="EC_SERVICES_REPO"):
        _ = commands.repo

    with pytest.raises(CommandError, match="EC_LOG_URL"):
        _ = commands.log_url


def test_context_is_honoured():
    commands = DemoCommands(
        ECContext(
            repo="https://github.com/epics-containers/bl01t-services",
            log_url="https://graylog2.diamond.ac.uk/{service_name}*",
        )
    )

    assert commands.repo == "https://github.com/epics-containers/bl01t-services"
    assert commands.log_url == "https://graylog2.diamond.ac.uk/{service_name}*"
