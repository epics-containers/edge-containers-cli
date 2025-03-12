"""TUI monitor for containerised IOCs."""

import logging
import threading
import time
from collections.abc import Callable
from functools import partial, total_ordering
from queue import Empty, Queue
from typing import Any, cast

import polars
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
    RichLog,
    Static,
)
from textual.widgets.data_table import RowKey
from textual.worker import get_current_worker

from edge_containers_cli.cmds.commands import Commands
from edge_containers_cli.definitions import ECLogLevels, emoji
from edge_containers_cli.logging import log


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

    def __init__(self, fetch_log: Callable, service_name: str) -> None:
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
            result = self.fetch_log(
                self.service_name,
                **{"prev": False},
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

    def __init__(self, commands, running_only: bool) -> None:
        super().__init__()

        self.commands = commands
        self.running_only = running_only
        self._indicator_lock = threading.Lock()
        self._service_indicators = {
            "name": [""],
            emoji.exclaim: [""],
        }
        iocs_df = self._get_services_df(self.running_only)
        self.columns = iocs_df.columns
        self._polling_rate_hz = 1

    def compose(self) -> ComposeResult:
        table: DataTable[Text] = DataTable(
            id="body_table",
            header_height=1,
            show_cursor=False,
            zebra_stripes=True,
        )
        table.focus()

        for column_id in self.columns:
            heading = self._get_heading(column_id)
            table.add_column(heading, key=str(column_id))

        table.show_cursor = True
        table.cursor_type = "row"

        yield table

    def _get_heading(self, column_id: str):
        if column_id == self.sort_column_id:
            heading = Text(column_id, justify="center")
        else:
            heading = Text(column_id, justify="center").on(
                click=f"app.sort('{column_id}')"
            )

        return heading

    def on_mount(self) -> None:
        self.do_polling()

    @work(exclusive=True, thread=True)
    def do_polling(self):
        worker = get_current_worker()

        while not worker.is_cancelled:
            result = self._get_services_df(self.running_only)
            self.app.call_from_thread(partial(self.populate_table, result))
            time.sleep(1 / self._polling_rate_hz)

    def _get_services_df(self, running_only):
        services_df = self.commands._get_services(running_only)  # noqa: SLF001
        services_df = services_df.with_columns(
            polars.when(polars.col("ready"))
            .then(polars.lit(emoji.check_mark))
            .otherwise(polars.lit(emoji.cross_mark))
            .alias("ready")
        )
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
                self._service_indicators[emoji.exclaim][index] = indicator
            else:
                self._service_indicators["name"].append(name)
                self._service_indicators[emoji.exclaim].append(indicator)

    def watch_sort_column_id(self, sort_column_id: str) -> None:
        """Called when the sort_column_id attribute changes."""
        table = self.query_one("#body_table", DataTable)

        # Reformat headings based on new sorted column
        for i, _column in enumerate(self.columns):
            table.ordered_columns[i].label = self._get_heading(_column)

        sorted_col = self.columns.index(sort_column_id)

        table.sort(table.ordered_columns[sorted_col].key, reverse=False)

    def populate_table(self, iocs_df) -> None:
        """Method to render the TUI table."""
        table = self.query_one("#body_table", DataTable)

        curr_ioc_set = set(table.rows)
        new_ioc_set = set()

        new_iocs = iocs_df.to_dicts()
        new_iocs = sorted(new_iocs, key=lambda d: d["name"])

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
                        Color.parse("white"),
                        justify="center",
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
                    table.update_cell(row_key, cell["col_key"], cell["contents"])

        # If any IOC has been removed, remove it from the table
        for old_row_key in curr_ioc_set - new_ioc_set:
            table.remove_row(old_row_key)

        # Sort by column
        table.sort(self.sort_column_id, reverse=False)


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
        Binding("m", "monitor_logs", "Monitor logs", show=False),
    ]

    def __init__(
        self,
        commands: Commands,
        running_only: bool,
    ) -> None:
        super().__init__()

        self.commands = commands
        self.running_only = running_only
        self.beamline = commands.target
        self.busy_services: ThreadsafeSet = ThreadsafeSet()
        self._queue: Queue[Callable] = Queue()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        with Vertical():
            with Static(id="ioc_table_container"):
                self.table = IocTable(self.commands, self.running_only)
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
                    table.update_indicator_threadsafe(service_name, emoji.road_works)
                    command(service_name)
                    table.update_indicator_threadsafe(service_name, emoji.none)
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
                            service_name, emoji.hour_glass
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
            # Convert to corresponding bool
            ready = self._get_highlighted_cell("ready") == emoji.check_mark

            if ready:
                command = self.commands._get_logs  # noqa: SLF001
                self.push_screen(LogsScreen(command, service_name))
            else:
                log.info(f"Ignore request for logs - {service_name} not ready")
        else:
            log.info("No services available to perform: 'logs'")

    def action_sort(self, col_name: str = "") -> None:
        """An action to sort the table rows by column heading."""
        if col_name != "":
            # If col_name is provided, sort by that column
            # e.g. if a column heading is clicked
            new_col = col_name
        else:
            # If no column name is provided (e.g. by pressing the key bind),
            # then just cycle to the next column
            table = self.query_one(IocTable)
            col_name = table.sort_column_id
            cols = table.columns
            col_index = cols.index(col_name)
            new_col = cols[0 if col_index + 1 > 3 else col_index + 1]
        self.update_sort_key(new_col)

    def action_monitor_logs(self) -> None:
        """Get a new hello and update the content area."""
        collapsed_state = self.query_one(Collapsible).collapsed
        self.query_one(Collapsible).collapsed = not collapsed_state

    def update_sort_key(self, col_name: str) -> None:
        """Method called to update the table sort key attribute."""
        table = self.query_one(IocTable)
        log.info(f"New sort key '{col_name}'")
        table.sort_column_id = col_name


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
