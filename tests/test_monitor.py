"""The `ec monitor` TUI shows the same columns as `ec ps`."""

import asyncio

from textual.widgets import DataTable
from textual.widgets.data_table import RowKey

from edge_containers_cli.cmds.demo_commands import DemoCommands
from edge_containers_cli.cmds.monitor import MonitorApp, cell_color
from edge_containers_cli.definitions import ECContext, Emoji
from edge_containers_cli.logging import log


def test_monitor_columns():
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)
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
        table = asyncio.run(run())
    finally:
        # MonitorLogs swaps the logger's handler for its own widget
        log.handlers[:] = handlers

    columns = [str(column.key.value) for column in table.ordered_columns]
    # the description is each row's label, not a column
    assert columns == [
        "name",
        "health",
        "sync",
        "version",
        "last sync",
        "properties",
        Emoji.exclaim,
    ]

    assert table.row_count == 8
    row = table.get_row("demo-ea-00")
    cells = dict(zip(columns, map(str, row), strict=True))
    assert cells["health"] == "Healthy"
    assert cells["sync"] == "Synced"
    assert cells["last sync"] == "2024-10-22T11:23:08Z"
    assert cells["properties"] == "location=bench-0"
    assert str(table.rows[RowKey("demo-ea-00")].label) == "demo-device-00"


def test_monitor_status_colors():
    assert cell_color("health", "Healthy").rgb == (0, 128, 0)
    assert cell_color("health", "Degraded").rgb == (255, 0, 0)
    assert cell_color("health", "Healthy (Stopped)").rgb == (128, 128, 128)
    assert cell_color("sync", "OutOfSync").rgb == (255, 255, 0)
    assert cell_color("version", "Healthy").rgb == (255, 255, 255)
