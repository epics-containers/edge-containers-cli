"""The `ec monitor` TUI shows the same columns as `ec ps`."""

import asyncio

from textual.widgets import DataTable

from edge_containers_cli.cmds.demo_commands import DemoCommands
from edge_containers_cli.cmds.monitor import SORT_ARROW, MonitorApp, cell_color
from edge_containers_cli.definitions import ECContext, Emoji
from edge_containers_cli.logging import log


async def _run_table(app: MonitorApp) -> DataTable:
    handlers = list(log.handlers)

    async def run() -> DataTable:
        async with app.run_test() as pilot:
            table = app.query_one("#body_table", DataTable)
            for _ in range(50):
                if table.row_count:
                    break
                await pilot.pause(0.1)
            return table

    try:
        return await run()
    finally:
        # MonitorLogs swaps the logger's handler for its own widget
        log.handlers[:] = handlers


def test_monitor_columns():
    """Default `ec monitor` columns match default `ec ps`: description is
    shown, properties is opt-in (-w/--wide), like the ec ps CLI."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)
    table = asyncio.run(_run_table(app))

    columns = [str(column.key.value) for column in table.ordered_columns]
    assert columns == [
        "name",
        "health",
        "sync",
        "version",
        "last sync",
        "description",
        Emoji.exclaim,
    ]

    assert table.row_count == 8
    row = table.get_row("demo-ea-00")
    cells = dict(zip(columns, map(str, row), strict=True))
    assert cells["health"] == "Healthy"
    assert cells["sync"] == "Synced"
    assert cells["last sync"] == "2024-10-22T11:23:08Z"
    assert cells["description"] == "demo-device-00"


def test_monitor_columns_wide():
    """`ec monitor --wide` adds properties, as `ec ps --wide` does."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False, wide=True)
    table = asyncio.run(_run_table(app))

    columns = [str(column.key.value) for column in table.ordered_columns]
    assert columns == [
        "name",
        "health",
        "sync",
        "version",
        "last sync",
        "description",
        "properties",
        Emoji.exclaim,
    ]

    row = table.get_row("demo-ea-00")
    cells = dict(zip(columns, map(str, row), strict=True))
    assert cells["properties"] == "location=bench-0"


def test_monitor_columns_left_justified():
    """Headers and cells are left-justified, like `ec ps`'s rich Table
    (whose columns default to justify="left")."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)
    table = asyncio.run(_run_table(app))

    for column in table.ordered_columns:
        assert column.label.justify == "left"

    row_key = next(iter(table.rows))
    for column in table.ordered_columns:
        cell = table.get_cell(row_key, column.key)
        assert cell.justify == "left"


def test_monitor_sort_arrow_cycles():
    """The sort arrow marks the current sort column's header, and only
    that header, and moves when the sort key cycles (the 'o' binding /
    action_sort). The table only has a sort key, no direction (always
    ascending), so one arrow is expected rather than a flipping pair."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)
    handlers = list(log.handlers)

    def heading(table: DataTable, column_id: str) -> str:
        col = next(c for c in table.ordered_columns if str(c.key.value) == column_id)
        return str(col.label)

    async def run() -> None:
        async with app.run_test() as pilot:
            table = app.query_one("#body_table", DataTable)
            for _ in range(50):
                if table.row_count:
                    break
                await pilot.pause(0.1)

            # default sort column is "name"
            assert heading(table, "name") == f"name {SORT_ARROW}"
            assert heading(table, "health") == "health"

            await pilot.press("o")
            await pilot.pause()

            assert heading(table, "name") == "name"
            assert heading(table, "health") == f"health {SORT_ARROW}"

    try:
        asyncio.run(run())
    finally:
        log.handlers[:] = handlers


def test_monitor_status_colors():
    assert cell_color("health", "Healthy").rgb == (0, 128, 0)
    assert cell_color("health", "Degraded").rgb == (255, 0, 0)
    # argocd-monitor flags a stopped app with a red "Stopped" badge; ec
    # folds that into "Healthy (Stopped)" and colours it the same red as
    # Degraded.
    assert cell_color("health", "Healthy (Stopped)").rgb == (255, 0, 0)
    assert cell_color("sync", "OutOfSync").rgb == (255, 255, 0)
    assert cell_color("version", "Healthy").rgb == (255, 255, 255)
