"""The `ec monitor` TUI shows the same columns as `ec ps`."""

import asyncio
from collections.abc import Awaitable, Callable

import polars
from textual.app import App
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from edge_containers_cli.cmds.demo_commands import DemoCommands
from edge_containers_cli.cmds.monitor import (
    ACTION_REFRESH_DELAY,
    ACTION_REFRESH_FOLLOW_UP_DELAY,
    SORT_ARROW_ASC,
    SORT_ARROW_DESC,
    IocTable,
    MonitorApp,
    cell_color,
)
from edge_containers_cli.definitions import ECContext
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


async def _interact(
    app: MonitorApp,
    body: Callable[["object", DataTable], Awaitable[None]],
    size: tuple[int, int] | None = None,
) -> None:
    """Run `body(pilot, table)` against a mounted, loaded MonitorApp,
    restoring the log handlers MonitorLogs swaps out. `size` forces the
    terminal size (defaults to run_test's own default, 80x24)."""
    handlers = list(log.handlers)

    async def run() -> None:
        run_test_cm = app.run_test() if size is None else app.run_test(size=size)
        async with run_test_cm as pilot:
            table = app.query_one("#body_table", DataTable)
            for _ in range(50):
                if table.row_count:
                    break
                await pilot.pause(0.1)
            await body(pilot, table)

    try:
        await run()
    finally:
        log.handlers[:] = handlers


def _visible_window(table: DataTable):
    """The table's currently visible content region, at its current
    scroll offset."""
    return table.scrollable_content_region.at_offset(table.scroll_offset)


def _column_region(table: DataTable, column_id: str):
    """The full region (header + rows) of the named column, however far
    off-screen it currently is."""
    index = next(
        i for i, c in enumerate(table.ordered_columns) if str(c.key.value) == column_id
    )
    return table._get_column_region(index)  # noqa: SLF001


def _heading(table: DataTable, column_id: str) -> str:
    col = next(c for c in table.ordered_columns if str(c.key.value) == column_id)
    return str(col.label)


def _sorted_column(table: DataTable, columns: list[str]) -> tuple[str, bool]:
    """Return (column_id, is_descending) for whichever visible column's
    header currently carries a sort arrow. Asserts exactly one does."""
    marked = []
    for col_id in columns:
        text = _heading(table, col_id)
        if text.endswith(SORT_ARROW_ASC):
            marked.append((col_id, False))
        elif text.endswith(SORT_ARROW_DESC):
            marked.append((col_id, True))
    assert len(marked) == 1, f"expected exactly one sort arrow, got {marked}"
    return marked[0]


def _name_column_key(table: DataTable) -> ColumnKey:
    return next(c.key for c in table.ordered_columns if str(c.key.value) == "name")


def _row_names(table: DataTable) -> list[str]:
    name_key = _name_column_key(table)
    return [str(table.get_cell(row.key, name_key)) for row in table.ordered_rows]


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


def test_monitor_sort_cycle_default_columns():
    """The 'o' binding (action_sort with no column) cycles the sort arrow
    through every visible column, in display order, wrapping back to the
    start. Exactly one header carries the arrow at every step, always
    ascending, and description gets it (it's a real column now, unlike the
    old row-label bug)."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        columns = [str(c.key.value) for c in table.ordered_columns]
        assert "description" in columns
        assert "properties" not in columns
        # every column the cycle visits has a real text header
        assert all(c.isascii() and c.strip() for c in columns)

        # default sort column is "name", ascending
        assert _sorted_column(table, columns) == ("name", False)

        for expected_column in columns[1:] + columns[:1]:
            await pilot.press("o")
            await pilot.pause()
            assert _sorted_column(table, columns) == (expected_column, False)

    asyncio.run(_interact(app, body))


def test_monitor_sort_cycle_wide_columns():
    """Same as above with --wide: properties joins the cycle too."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False, wide=True)

    async def body(pilot, table: DataTable) -> None:
        columns = [str(c.key.value) for c in table.ordered_columns]
        assert "description" in columns
        assert "properties" in columns
        assert all(c.isascii() and c.strip() for c in columns)

        assert _sorted_column(table, columns) == ("name", False)

        for expected_column in columns[1:] + columns[:1]:
            await pilot.press("o")
            await pilot.pause()
            assert _sorted_column(table, columns) == (expected_column, False)

    asyncio.run(_interact(app, body))


def test_monitor_sort_direction_toggle_key():
    """The 'd' binding (action_toggle_sort_direction) flips the current
    sort column's direction, and row order reverses, without changing which
    column is sorted."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        columns = [str(c.key.value) for c in table.ordered_columns]
        assert _sorted_column(table, columns) == ("name", False)
        ascending_names = _row_names(table)
        assert ascending_names == sorted(ascending_names)

        await pilot.press("d")
        await pilot.pause()

        assert _sorted_column(table, columns) == ("name", True)
        assert _row_names(table) == list(reversed(ascending_names))

        # toggling back returns to ascending
        await pilot.press("d")
        await pilot.pause()

        assert _sorted_column(table, columns) == ("name", False)
        assert _row_names(table) == ascending_names

    asyncio.run(_interact(app, body))


def test_monitor_sort_header_click_new_column():
    """Clicking a header that isn't the sort column (simulated via
    action_sort(col_name), exactly what the header's click action runs)
    makes it the sort column, ascending."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        columns = [str(c.key.value) for c in table.ordered_columns]
        assert _sorted_column(table, columns) == ("name", False)

        app.action_sort("description")
        await pilot.pause()

        assert _sorted_column(table, columns) == ("description", False)

    asyncio.run(_interact(app, body))


def test_monitor_sort_header_click_current_column_toggles():
    """Clicking the header that's already the sort column toggles its
    direction instead of no-op'ing."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        columns = [str(c.key.value) for c in table.ordered_columns]
        assert _sorted_column(table, columns) == ("name", False)

        app.action_sort("name")
        await pilot.pause()
        assert _sorted_column(table, columns) == ("name", True)

        app.action_sort("name")
        await pilot.pause()
        assert _sorted_column(table, columns) == ("name", False)

    asyncio.run(_interact(app, body))


def test_monitor_sort_direction_survives_refresh():
    """A polling refresh (populate_table) must keep the table sorted in the
    chosen direction, not silently reset to ascending."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        ioc_table = app.query_one(IocTable)
        await pilot.press("d")  # name, descending
        await pilot.pause()
        descending_names = _row_names(table)
        assert descending_names == sorted(descending_names, reverse=True)

        # Simulate a polling refresh with freshly-fetched data
        ioc_table.populate_table(ioc_table._get_services_df(ioc_table.running_only))  # noqa: SLF001
        await pilot.pause()

        columns = [str(c.key.value) for c in table.ordered_columns]
        assert _sorted_column(table, columns) == ("name", True)
        assert _row_names(table) == descending_names

    asyncio.run(_interact(app, body))


def test_monitor_column_widens_on_refresh():
    """Columns are auto-width. When a polling refresh grows a cell's
    content - e.g. health becomes "Healthy (Stopped)" once a service is
    stopped - the column must widen to fit it, not stay sized for the
    shorter text it replaced (DataTable.update_cell needs
    update_width=True for this, which defaults to False)."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        ioc_table = app.query_one(IocTable)
        health_key = next(
            c.key for c in table.ordered_columns if str(c.key.value) == "health"
        )

        def health_width() -> int:
            return table.columns[health_key].content_width

        before_width = health_width()
        assert before_width >= len("Healthy")

        stopped_text = "Healthy (Stopped)"
        iocs_df = ioc_table._get_services_df(ioc_table.running_only)  # noqa: SLF001
        target_name = iocs_df["name"][0]
        iocs_df = iocs_df.with_columns(
            polars.when(polars.col("name") == target_name)
            .then(polars.lit(stopped_text))
            .otherwise(polars.col("health"))
            .alias("health")
        )

        # The same refresh path do_polling uses.
        ioc_table.populate_table(iocs_df)
        await pilot.pause()

        assert health_width() >= len(stopped_text)
        assert health_width() > before_width

    asyncio.run(_interact(app, body))


def test_monitor_sort_arrow_does_not_clip_header():
    """Every header must reserve room for " <arrow>", not just the sort
    column's, so a column doesn't need to grow - and clip the arrow while
    it's too narrow to fit it - the moment it becomes the sort column.
    "version" is a good column to prove this on: its demo data
    ("1.0.25" etc, 6 chars) is narrower than "version" (7 chars), so
    nothing forces the column wide enough by accident."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        version_key = next(
            c.key for c in table.ordered_columns if str(c.key.value) == "version"
        )

        def version_width() -> int:
            return table.columns[version_key].content_width

        app.action_sort("version")
        await pilot.pause()
        assert version_width() >= len(f"version {SORT_ARROW_ASC}")

        await pilot.press("d")
        await pilot.pause()
        assert version_width() >= len(f"version {SORT_ARROW_DESC}")

    asyncio.run(_interact(app, body))


def test_monitor_sort_scrolls_offscreen_column_into_view():
    """Cycling the sort key ('o') onto a column that's off-screen at a
    narrow terminal width scrolls the table horizontally so the column -
    header arrow included - is fully inside the viewport, without moving
    the row cursor or the vertical scroll. At 30 columns wide, "version"
    (the fourth default column) no longer fits alongside the earlier
    ones."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        ioc_table = app.query_one(IocTable)

        assert table.scroll_x == 0
        cursor_row_before = table.cursor_row
        scroll_y_before = table.scroll_y

        target = "version"
        target_region = _column_region(table, target)
        assert not _visible_window(table).contains_region(target_region), (
            "test setup: 'version' should start off-screen at this width"
        )

        while ioc_table.sort_column_id != target:
            await pilot.press("o")
            await pilot.pause()

        assert table.scroll_x > 0
        assert _visible_window(table).contains_region(target_region)
        assert table.cursor_row == cursor_row_before
        assert table.scroll_y == scroll_y_before

    asyncio.run(_interact(app, body, size=(30, 24)))


def test_monitor_sort_does_not_scroll_when_column_already_visible():
    """When every column already fits in the viewport (the default 80-wide
    terminal, as every other test in this file uses), cycling the sort key
    never scrolls the table - scroll_to_region's own "already visible"
    check makes this a no-op, covering the 'd' direction-toggle case too
    (it never changes which column is sorted, so there's never anything
    new to reveal)."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        ioc_table = app.query_one(IocTable)
        columns = [str(c.key.value) for c in table.ordered_columns]

        for _ in columns:
            await pilot.press("o")
            await pilot.pause()
            assert table.scroll_x == 0

        await pilot.press("d")
        await pilot.pause()
        assert table.scroll_x == 0
        assert ioc_table.sort_reverse

    asyncio.run(_interact(app, body))


def test_monitor_pointer_shape_override_point_exists():
    """MonitorApp overrides the private `App._set_pointer_shape` (see its
    docstring). If a Textual upgrade renames or removes it, the override
    silently stops applying and the OSC 22 leak below would come back
    without any test noticing - so pin the method's existence directly."""
    assert hasattr(App, "_set_pointer_shape")


def test_monitor_click_does_not_leak_osc22():
    """Textual's Kitty pointer-shape escape (OSC 22, `ESC ] 22 ; <shape>
    BEL`) is written unconditionally on mouse events, with no terminal
    capability check; a terminal that doesn't consume it prints it as
    literal text over the Header icon (e.g. "]22;text" after clicking the
    table). MonitorApp overrides `_set_pointer_shape` to a no-op, so no
    such escape - or anything else via that path - should reach the
    driver."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)
    handlers = list(log.handlers)

    async def run() -> None:
        async with app.run_test() as pilot:
            table = app.query_one("#body_table", DataTable)
            for _ in range(50):
                if table.row_count:
                    break
                await pilot.pause(0.1)

            writes: list[str] = []
            driver = app._driver  # noqa: SLF001
            assert driver is not None
            orig_write = driver.write

            def spy(data: str) -> None:
                writes.append(data)
                orig_write(data)

            driver.write = spy

            await pilot.click(table)
            await pilot.pause()

            assert not any("\x1b]22;" in chunk for chunk in writes)

    try:
        asyncio.run(run())
    finally:
        log.handlers[:] = handlers


def test_monitor_action_schedules_refresh(monkeypatch):
    """Completing an action (start/stop/restart) doesn't wait for the next
    poll tick to show its effect: MonitorApp._schedule_action_refresh
    schedules a refresh - through the same path (IocTable.refresh_now)
    the poll loop uses - ACTION_REFRESH_DELAY after the command returns,
    plus a follow-up ACTION_REFRESH_FOLLOW_UP_DELAY later, since Argo can
    take a moment longer to catch up. `set_timer` is captured instead of
    actually waited on, so this asserts the two refreshes are scheduled -
    at the right delays, targeting refresh_now - independent of (and
    without needing to wait out) the regular 1s poll timer, which keeps
    running untouched throughout."""
    app = MonitorApp(DemoCommands(ECContext()), running_only=False)

    async def body(pilot, table: DataTable) -> None:
        ioc_table = app.query_one(IocTable)

        scheduled: list[tuple[float, Callable]] = []

        def fake_set_timer(delay, callback, *args, **kwargs):
            scheduled.append((delay, callback))

        monkeypatch.setattr(app, "set_timer", fake_set_timer)

        refresh_calls = 0

        def counting_refresh_now() -> None:
            nonlocal refresh_calls
            refresh_calls += 1

        monkeypatch.setattr(ioc_table, "refresh_now", counting_refresh_now)

        # Start the highlighted service and confirm the dialog - the real
        # start/confirm flow, not a direct call to the scheduling method.
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("y")

        # Wait for the queued action to finish (DemoCommands.start sleeps
        # briefly) and schedule its refreshes.
        for _ in range(50):
            if len(scheduled) == 2:
                break
            await pilot.pause(0.1)

        assert [delay for delay, _ in scheduled] == [
            ACTION_REFRESH_DELAY,
            ACTION_REFRESH_FOLLOW_UP_DELAY,
        ]
        assert all(callback is counting_refresh_now for _, callback in scheduled)

        # Firing the scheduled callbacks - as the real timers eventually
        # would - drives exactly those two refreshes, no more.
        for _, callback in scheduled:
            callback()
        assert refresh_calls == 2

    asyncio.run(_interact(app, body))


def test_monitor_status_colors():
    assert cell_color("health", "Healthy").rgb == (0, 128, 0)
    assert cell_color("health", "Degraded").rgb == (255, 0, 0)
    # argocd-monitor flags a stopped app with a red "Stopped" badge; ec
    # folds that into "Healthy (Stopped)" and colours it the same red as
    # Degraded.
    assert cell_color("health", "Healthy (Stopped)").rgb == (255, 0, 0)
    assert cell_color("sync", "OutOfSync").rgb == (255, 255, 0)
    assert cell_color("version", "Healthy").rgb == (255, 255, 255)
