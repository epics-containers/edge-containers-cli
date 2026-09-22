"""TUI monitor for containerised IOCs."""

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from functools import partial, total_ordering
from queue import Empty, Queue
from typing import Any, cast

import polars
from rich.cells import cell_len
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Grid, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Label,
    LoadingIndicator,
    RichLog,
    Static,
)
from textual.widgets.data_table import RowKey
from textual.worker import get_current_worker

from edge_containers_cli.cmds.commands import (
    HEALTHY,
    STOPPED_SUFFIX,
    WIDE_COLUMNS,
    CommandError,
    Commands,
)
from edge_containers_cli.definitions import ECLogLevels, Emoji
from edge_containers_cli.git import GitError
from edge_containers_cli.logging import log
from edge_containers_cli.shell import ShellError
from edge_containers_cli.utils import _AsyncFuncType, _run_async

WHITE = Color.parse("white")

# Marks the current sort column's header and its direction - see
# _get_heading.
SORT_ARROW_ASC = "▲"
SORT_ARROW_DESC = "▼"

# Every header reserves this much trailing width for " <arrow>", whether or
# not it is currently the sort column - see _get_heading. A column's width
# is only computed once, from the header Text passed to add_column(); when
# the sort key later moves, _apply_sort() swaps a column's label in place
# without recomputing its width, so a header that grew an arrow it hadn't
# budgeted for would clip.
_SORT_SUFFIX_WIDTH = 1 + max(cell_len(SORT_ARROW_ASC), cell_len(SORT_ARROW_DESC))

# colours for the Argo CD health and sync vocabularies, as in
# argocd-monitor's status badges. A stopped service's health ends in
# STOPPED_SUFFIX and is shown grey.
STATUS_COLORS = {
    "health": {
        HEALTHY: Color.parse("green"),
        "Progressing": Color.parse("dodgerblue"),
        "Degraded": Color.parse("red"),
        "Missing": Color.parse("yellow"),
        "Suspended": Color.parse("grey"),
        "Unknown": Color.parse("grey"),
    },
    "sync": {
        "Synced": Color.parse("green"),
        "OutOfSync": Color.parse("yellow"),
        "Unknown": Color.parse("grey"),
    },
}


def cell_color(column: str, value: Any) -> Color:
    # argocd-monitor flags a stopped app with a separate red "Stopped"
    # badge (Badge variant="destructive") next to its health badge, whatever
    # the underlying health colour. ec folds that into one "Healthy
    # (Stopped)" string, so show it in the same red as Degraded.
    if column == "health" and str(value).endswith(STOPPED_SUFFIX):
        return STATUS_COLORS["health"]["Degraded"]
    return STATUS_COLORS.get(column, {}).get(str(value), WHITE)


class ConfirmScreen(ModalScreen[bool], inherit_bindings=False):
    BINDINGS = [
        Binding("y,enter", "option_yes", "Yes"),
        Binding("n,c,escape", "option_cancel", "Cancel"),
    ]

    def __init__(self, service_name: str, type_action: str) -> None:
        super().__init__()

        self.service_name = service_name
        self.type_action = type_action

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                f"Are you sure you want to {self.type_action} {self.service_name}?",
                id="question",
            ),
            Button("Yes", variant="error", id="yes"),
            Button("No", variant="primary", id="cancel"),
            id="dialog",
        )
        yield Footer()

    @on(Button.Pressed, "#yes")
    def action_option_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def action_option_cancel(self) -> None:
        self.dismiss(False)


class ErrorScreen(ModalScreen[bool], inherit_bindings=False):
    BINDINGS = [
        Binding("y,enter", "option_ok", "OK"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                f"Error: {self.message}",
                id="error_ok",
            ),
            Button("OK", variant="error", id="okay"),
            id="dialog",
        )
        yield Footer()

    @on(Button.Pressed, "#okay")
    def action_option_ok(self) -> None:
        self.dismiss(True)


class LogsScreen(ModalScreen, inherit_bindings=False):
    """Screen to display IOC logs."""

    BINDINGS = [
        Binding("q", "close_screen", "Close"),
        Binding("up,w,k", "scroll_up", "Scroll Up", show=False),
        Binding("down,s,j", "scroll_down", "Scroll Down", show=False),
        Binding("left,h", "scroll_left", "Scroll Left", show=False),
        Binding("right,l", "scroll_right", "Scroll Right", show=False),
        Binding("home,G", "scroll_home", "Scroll Home", show=True, key_display="Home"),
        Binding("end,g", "scroll_end", "Scroll End", show=True, key_display="End"),
        Binding("pageup,b", "page_up", "Page Up", show=False),
        Binding("pagedown,space", "page_down", "Page Down", show=False),
        Binding("f", "follow_logs", "Follow Logs", show=True),
    ]

    def __init__(self, fetch_log: _AsyncFuncType, service_name: str) -> None:
        super().__init__()
        self.fetch_log = fetch_log
        self.service_name = service_name
        self.auto_scroll = False
        self._polling_rate_hz = 1

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(highlight=True, id="log")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"{self.service_name} logs"
        self.do_polling()

    @work(exclusive=True, thread=True)
    def do_polling(self):
        worker = get_current_worker()

        while not worker.is_cancelled:
            result = _run_async(
                self.fetch_log(
                    self.service_name,
                    **{"prev": False},
                )
            )
            self.app.call_from_thread(partial(self.update_logs, result))
            time.sleep(1 / self._polling_rate_hz)

    def update_logs(self, log_text):
        log = self.query_one(RichLog)
        curr_x = log.scroll_x
        curr_y = log.scroll_y
        log.clear()
        log.write(
            Syntax(log_text, "bash", line_numbers=True),
            width=80,
            expand=True,
            shrink=False,
            scroll_end=False,
        )
        if self.auto_scroll:
            log.scroll_end(animate=False)
        else:
            log.scroll_x = curr_x
            log.scroll_y = curr_y

    def action_close_screen(self) -> None:
        self.app.pop_screen()

    def action_scroll_up(self) -> None:
        log = self.query_one(RichLog)
        log.action_scroll_up()

    def action_scroll_down(self) -> None:
        log = self.query_one(RichLog)
        log.action_scroll_down()

    def action_scroll_home(self) -> None:
        log = self.query_one(RichLog)
        log.action_scroll_home()

    def action_scroll_end(self) -> None:
        log = self.query_one(RichLog)
        log.action_scroll_end()

    def action_page_down(self) -> None:
        log = self.query_one(RichLog)
        log.action_page_down()

    def action_page_up(self) -> None:
        log = self.query_one(RichLog)
        log.action_page_up()

    def action_follow_logs(self) -> None:
        log = self.query_one(RichLog)
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            log.scroll_end(animate=False)


@total_ordering
class SortableText(Text):
    __slots__ = ("value",)

    def __init__(
        self,
        value: Any,
        text: str,
        color: Color,
        justify: Any = "left",  # "Any" is a hack: justify should be Literal
    ) -> None:
        self.value = value
        super().__init__(
            str(text),
            Style(color=color.rich_color),
            justify=justify,
        )

    def __lt__(self, other: Any) -> bool:
        if type(other) is not SortableText:
            return NotImplemented

        # Handle None as values
        match self.value, other.value:
            case (None, None) | (None, _):
                return False
            case (_, None):
                return True
            case _:
                return cast(bool, self.value < other.value)

    def __gt__(self, other: Any) -> bool:
        if type(other) is not SortableText:
            return NotImplemented

        # Handle None as values
        match self.value, other.value:
            case (None, None) | (_, None):
                return False
            case (None, _):
                return True
            case _:
                return cast(bool, self.value > other.value)

    def __eq__(self, other: Any) -> bool:
        if type(other) is not SortableText:
            return NotImplemented

        # Handle None as values
        match self.value, other.value:
            case (None, _) | (_, None):
                return False
            case (None, None):
                return True
            case _:
                return cast(bool, self.value == other.value)


class IocTable(Widget):
    """Widget to display the IOC table."""

    default_sort_column_id = "name"
    sort_column_id = reactive(default_sort_column_id, init=False)
    sort_reverse = reactive(False, init=False)

    def __init__(self, commands, running_only: bool, wide: bool = False) -> None:
        super().__init__()

        self.commands = commands
        self.running_only = running_only
        self.wide = wide
        self._indicator_lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._service_indicators = {
            "name": [""],
            Emoji.exclaim: [""],
        }
        self._polling_rate_hz = 1

    def compose(self) -> ComposeResult:
        yield LoadingIndicator()

        self.table: DataTable[Text] = DataTable(
            id="body_table",
            header_height=1,
            show_cursor=False,
            zebra_stripes=True,
        )
        self.table.focus()
        yield self.table

    def _get_heading(self, column_id: str):
        if column_id == self.sort_column_id:
            arrow = SORT_ARROW_DESC if self.sort_reverse else SORT_ARROW_ASC
            suffix = f" {arrow}"
        else:
            # Reserve the same width as " <arrow>" so this header doesn't
            # need to grow - and clip the arrow while it's too narrow - the
            # moment it becomes the sort column. See _SORT_SUFFIX_WIDTH.
            suffix = " " * _SORT_SUFFIX_WIDTH
        heading = Text(f"{column_id}{suffix}", justify="left")

        # Clicking any header sorts by it: a click on the current sort
        # column toggles its direction (set_sort_column), a click on
        # another column makes it the (ascending) sort column.
        return heading.on(click=f"app.sort('{column_id}')")

    def set_sort_column(self, column_id: str) -> None:
        """Called when a column header is clicked (or `app.sort(col)` is
        run directly). Toggles direction if it's already the sort column,
        otherwise makes it the sort column, ascending."""
        if column_id == self.sort_column_id:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column_id = column_id
            self.sort_reverse = False

    def cycle_sort_column(self) -> None:
        """Called by the 'o' binding: move the sort key to the next visible
        column, in display order, wrapping around, and reset to ascending."""
        col_index = self.columns.index(self.sort_column_id)
        self.sort_column_id = self.columns[(col_index + 1) % len(self.columns)]
        self.sort_reverse = False

    def toggle_sort_direction(self) -> None:
        """Called by the direction-toggle binding: flip the current sort
        column's direction without changing which column is sorted."""
        self.sort_reverse = not self.sort_reverse

    def on_mount(self) -> None:
        self.table.display = False  # hide until ready
        self.load_data()
        # self.do_polling()

    @work(thread=True)
    def load_data(self):
        iocs_df: polars.DataFrame = self._get_services_df(self.running_only)

        self.columns = iocs_df.columns
        if not self.wide:
            # match `ec ps`: properties are opt-in via --wide
            self.columns = [c for c in self.columns if c not in WIDE_COLUMNS]

        def _update():
            for column_id in self.columns:
                heading = self._get_heading(column_id)
                self.table.add_column(heading, key=str(column_id))

            self.query_one(LoadingIndicator).display = False
            self.table.display = True

            self.table.show_cursor = True
            self.table.cursor_type = "row"

            self.do_polling()

            self.sort_column_id = (
                self.default_sort_column_id
            )  # triggers watch_sort_column_id

        self.app.call_from_thread(_update)

    @work(exclusive=True, thread=True)
    def do_polling(self):
        worker = get_current_worker()

        while not worker.is_cancelled:
            result = self._get_services_df(self.running_only)
            self.app.call_from_thread(partial(self.populate_table, result))
            time.sleep(1 / self._polling_rate_hz)

    def _get_services_df(self, running_only):
        services_df = self.commands._get_services_df(running_only)  # noqa: SLF001
        indicators_df = polars.DataFrame(self._service_indicators)
        result = services_df.join(
            indicators_df,
            on="name",
            how="left",
        ).fill_null("")
        return result

    def update_indicator_threadsafe(self, name: str, indicator: str):
        with self._indicator_lock:
            if name in self._service_indicators["name"]:
                index = self._service_indicators["name"].index(name)
                self._service_indicators[Emoji.exclaim][index] = indicator
            else:
                self._service_indicators["name"].append(name)
                self._service_indicators[Emoji.exclaim].append(indicator)

    def watch_sort_column_id(self, sort_column_id: str) -> None:
        """Called when the sort_column_id attribute changes."""
        self._apply_sort()

    def watch_sort_reverse(self, sort_reverse: bool) -> None:  # noqa: FBT001
        """Called when the sort_reverse attribute changes (a direction
        toggle on the current sort column, with no column change)."""
        self._apply_sort()

    def _apply_sort(self) -> None:
        """(Re)draw every header to reflect sort_column_id/sort_reverse,
        and (re)sort the rows to match. Called whenever either changes."""
        table = self.query_one("#body_table", DataTable)

        # Reformat headings based on the current sort column and direction
        for i, _column in enumerate(self.columns):
            table.ordered_columns[i].label = self._get_heading(_column)

        sorted_col = self.columns.index(self.sort_column_id)

        table.sort(table.ordered_columns[sorted_col].key, reverse=self.sort_reverse)

    def populate_table(self, iocs_df) -> None:
        """Method to render the TUI table."""
        table = self.query_one("#body_table", DataTable)

        curr_ioc_set = set(table.rows)
        new_ioc_set = set()

        new_iocs: list[dict] = iocs_df.to_dicts()
        new_iocs = sorted(new_iocs, key=lambda d: d["name"])

        with self.app.batch_update():
            # For each IOC row
            for ioc in new_iocs:
                row_key = str(ioc["name"])
                new_ioc_set.add(RowKey(row_key))

                cells = [
                    {
                        "col_key": key,
                        "contents": SortableText(
                            ioc[key],
                            str(ioc[key]),
                            cell_color(key, ioc[key]),
                            justify="left",
                        ),
                    }
                    for key in self.columns
                ]

                if row_key not in table.rows:
                    table.add_row(
                        *[cell["contents"] for cell in cells],
                        key=row_key,
                    )
                else:
                    for cell in cells:
                        current = table.get_cell(row_key, cell["col_key"])
                        # only update if value has actually changed
                        if str(current) != str(cell["contents"]):
                            # update_width=True: a refreshed cell can grow
                            # (e.g. "Healthy" -> "Healthy (Stopped)") and the
                            # column must widen to fit, as it would for a
                            # freshly added row.
                            table.update_cell(
                                row_key,
                                cell["col_key"],
                                cell["contents"],
                                update_width=True,
                            )

            # If any IOC has been removed, remove it from the table
            for old_row_key in curr_ioc_set - new_ioc_set:
                table.remove_row(old_row_key)

            # Sort by column, preserving the current direction across
            # polling refreshes
            table.sort(self.sort_column_id, reverse=self.sort_reverse)


class MonitorLogHandler(logging.Handler):
    def __init__(self, rich_log: RichLog):
        super().__init__()
        self.rich_log = rich_log

    def emit(self, record: logging.LogRecord):
        log_entry = self.format(record)
        self.rich_log.write(Text(log_entry))


class MonitorLogs(Static):
    """Widget to display the monitor logs."""

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield RichLog(max_lines=25)

    def on_mount(self) -> None:
        rich_log = self.query_one(RichLog)
        handler = MonitorLogHandler(rich_log)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        log.addHandler(handler)
        log.removeHandler(log.handlers[0])  # Cut noise from main handler
        log.setLevel(ECLogLevels.INFO.value)


class MonitorApp(App):
    CSS_PATH = "monitor.tcss"

    BINDINGS = [
        Binding("escape", "close_application", "Exit"),
        Binding("s", "start_ioc", "Start IOC"),
        Binding("t", "stop_ioc", "Stop IOC"),
        Binding("r", "restart_ioc", "Restart IOC"),
        Binding("l", "ioc_logs", "IOC Logs"),
        Binding("o", "sort", "Sort"),
        Binding("d", "toggle_sort_direction", "Direction"),
        Binding("m", "monitor_logs", "Monitor logs", show=False),
    ]

    def __init__(
        self,
        commands: Commands,
        running_only: bool,
        wide: bool = False,
    ) -> None:
        super().__init__()

        self.commands = commands
        self.running_only = running_only
        self.wide = wide
        self.beamline = commands.target
        self.busy_services: ThreadsafeSet = ThreadsafeSet()
        self._queue: Queue[Callable] = Queue()

    def _set_pointer_shape(self, shape: str) -> None:
        """Silence Textual's Kitty pointer-shape escape (OSC 22).

        `App._set_pointer_shape` (private API - hence the `textual<9` pin in
        pyproject.toml) writes `ESC ] 22 ; <shape> BEL` unconditionally,
        with no terminal-capability check, right after parking the cursor
        at (0, 0) for the frame. A terminal that doesn't consume OSC 22
        prints it as literal text over the Header's icon instead - e.g.
        clicking anywhere in the table leaves "]22;text" stuck there. ec's
        monitor doesn't need the pointer shape changed, so this overrides
        it to do nothing rather than trying to detect terminal support.
        """

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        with Vertical():
            with Static(id="ioc_table_container"):
                self.table = IocTable(self.commands, self.running_only, self.wide)
                yield ScrollableContainer(self.table)
            yield Collapsible(
                MonitorLogs(),
                title="Monitor Logs (m)",
                collapsed=True,
                id="collapsible_container",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"{self.beamline} Services Monitor"
        self.do_work()

    @work(exclusive=True, thread=True)
    def do_work(self):
        worker = get_current_worker()
        while not worker.is_cancelled:
            try:
                job = self._queue.get(timeout=1)
                job()
                self._queue.task_done()
            except (CommandError, ShellError, GitError) as e:
                self.app.call_from_thread(
                    partial(self.push_screen, ErrorScreen(str(e)))
                )
            except Empty:
                pass

    def action_close_application(self) -> None:
        """Provide another way of exiting the app along with CTRL+C."""
        self.exit()

    def _get_highlighted_cell(self, col_key: str) -> str | None:
        table = self.get_widget_by_id("body_table")
        assert isinstance(table, DataTable)
        # Fetches hightlighted row ID (integer)
        row = table.cursor_row
        if table.ordered_rows:
            ioc_row = table.ordered_rows[row]
            col_keys = [ord_col.key.value for ord_col in table.ordered_columns]
            col_i = col_keys.index(col_key)
            ioc_col = table.ordered_columns[col_i]
            cell: str | SortableText = table.get_cell(ioc_row.key, ioc_col.key)
            # SortableText inherits __str__() from Text
            return str(cell)

    def _get_service_name(self) -> str | None:
        if service_name := self._get_highlighted_cell("name"):
            return service_name

    def _do_confirmed_action(self, action: str, command: Callable):
        if service_name := self._get_service_name():
            table = self.query_one(IocTable)

            def do_task(command, service_name):
                def _do_task():
                    try:
                        table.update_indicator_threadsafe(
                            service_name, Emoji.road_works
                        )
                        _run_async(command(service_name))
                    finally:
                        table.update_indicator_threadsafe(service_name, Emoji.none)
                        self.busy_services.remove(service_name)

                return _do_task

            def after_dismiss_callback(start: bool | None) -> None:
                """Called when ConfirmScreen is dismissed."""
                if start:
                    if service_name in self.busy_services:
                        log.info(f"Skipped {action}: {service_name} is busy")
                        return None
                    else:
                        log.info(f"Scheduled: {action} {service_name}")
                        self.busy_services.add(service_name)
                        table.update_indicator_threadsafe(
                            service_name, Emoji.hour_glass
                        )
                        self._queue.put(do_task(command, service_name))

            self.push_screen(
                ConfirmScreen(service_name, action),
                after_dismiss_callback,
            )
        else:
            log.info(f"No services available to perform: '{action}'")

    def action_start_ioc(self) -> None:
        """Start the IOC that is currently highlighted."""
        self._do_confirmed_action("start", self.commands.start)

    def action_stop_ioc(self) -> None:
        """Stop the IOC that is currently highlighted."""
        self._do_confirmed_action("stop", self.commands.stop)

    def action_restart_ioc(self) -> None:
        """Restart the IOC that is currently highlighted."""
        self._do_confirmed_action("restart", self.commands.restart)

    def action_ioc_logs(self) -> None:
        """Display the logs of the IOC that is currently highlighted."""
        if service_name := self._get_service_name():
            if self._get_highlighted_cell("health") == HEALTHY:
                command = self.commands._get_logs  # noqa: SLF001
                self.push_screen(LogsScreen(command, service_name))
            else:
                log.info(f"Ignore request for logs - {service_name} not healthy")
        else:
            log.info("No services available to perform: 'logs'")

    def action_sort(self, col_name: str = "") -> None:
        """An action to sort the table rows by column heading."""
        table = self.query_one(IocTable)
        if col_name != "":
            # col_name is provided when a column heading is clicked: sort by
            # it (toggling direction if it's already the sort column).
            log.info(f"Sort column selected: '{col_name}'")
            table.set_sort_column(col_name)
        else:
            # No column name (the 'o' key bind): cycle to the next visible
            # column, resetting to ascending.
            table.cycle_sort_column()
            log.info(f"New sort key '{table.sort_column_id}'")

    def action_toggle_sort_direction(self) -> None:
        """An action to flip the current sort column's direction."""
        table = self.query_one(IocTable)
        table.toggle_sort_direction()
        direction = "descending" if table.sort_reverse else "ascending"
        log.info(f"Sort direction: {direction}")

    def action_monitor_logs(self) -> None:
        """Get a new hello and update the content area."""
        collapsed_state = self.query_one(Collapsible).collapsed
        self.query_one(Collapsible).collapsed = not collapsed_state


class ThreadsafeSet:
    def __init__(self):
        self._set = set()
        self._lock = threading.Lock()

    def add(self, item):
        with self._lock:
            self._set.add(item)

    def remove(self, element):
        with self._lock:
            self._set.remove(element)

    def __contains__(self, item):
        return item in self._set
