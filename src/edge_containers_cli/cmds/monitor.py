"""TUI monitor for containerised IOCs."""

from functools import total_ordering
from threading import Thread
from time import sleep
from typing import Any, Union, cast

import polars
from rich.style import Style
from rich.text import Text

# from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Grid
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Label
from textual.widgets.data_table import RowKey

from edge_containers_cli.cmds.commands import Commands

# @on(Button.Pressed, "#startstop")
# def startstop(self, event: Button.Pressed) -> None:
#     """Event handler called when a button is pressed."""
#     pass

# @on(Button.Pressed, "#logs")
# def logs(self, event: Button.Pressed) -> None:
#     """Event handler called when a button is pressed."""
#     pass


class OptionScreen(ModalScreen[bool]):
    def __init__(self, service_name: str) -> None:
        super().__init__()

        self.service_name = service_name
        self.type_action = "stop"

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.action_option_yes()
        else:
            self.action_option_cancel()

    def action_option_yes(self) -> None:
        self.dismiss(True)

    def action_option_cancel(self) -> None:
        self.dismiss(False)


class StartScreen(OptionScreen):
    """Screen with dialog to start service."""

    def __init__(self, service_name: str) -> None:
        super().__init__(service_name)

        self.type_action = "start"


class StopScreen(OptionScreen):
    """Screen with dialog to stop service."""

    def __init__(self, service_name: str) -> None:
        super().__init__(service_name)

        self.type_action = "stop"


class RestartScreen(OptionScreen):
    """Screen with dialog to restart service."""

    def __init__(self, service_name: str) -> None:
        super().__init__(service_name)

        self.type_action = "restart"


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
        if type(other) != SortableText:
            return NotImplemented
        return cast(bool, self.value < other.value)

    def __gt__(self, other: Any) -> bool:
        if type(other) != SortableText:
            return NotImplemented
        return cast(bool, self.value > other.value)

    def __eq__(self, other: Any) -> bool:
        if type(other) != SortableText:
            return NotImplemented
        return cast(bool, self.value == other.value)


class IocTable(Widget):
    """Widget to display the IOC table."""

    default_sort_column_id = "name"
    # init=False otherwise triggers table query before yielded in compose
    sort_column_id = reactive(default_sort_column_id, init=False)

    def __init__(self, commands, all) -> None:
        super().__init__()

        self.commands = commands
        self.all = all
        self.iocs_df = self.commands.get_services(self.all)

        self._polling = True
        self._poll_thread = Thread(target=self._poll_services)
        self._poll_thread.start()
        self._get_iocs()

    def _poll_services(self):
        while self._polling:
            # ioc list data table update loop
            print()
            self.iocs_df = self.commands.get_services(self.all)
            sleep(0.5)

    def stop(self):
        self._polling = False
        self._poll_thread.join()

    def _get_iocs(self) -> None:
        iocs = self._convert_df_to_list(self.iocs_df)
        # give up the GIL to other threads
        sleep(0)
        self.iocs = sorted(iocs, key=lambda d: d["name"])
        exclude = ["deployed", "image"]

        for i, ioc in enumerate(self.iocs):
            ioc = {key: value for key, value in ioc.items() if key not in exclude}
            self.iocs[i] = ioc
        self.columns = [key for key in self.iocs[0].keys() if key not in exclude]

    def _convert_df_to_list(self, iocs_df: Union[polars.DataFrame, list]) -> list[dict]:
        if isinstance(iocs_df, polars.DataFrame):
            iocs = iocs_df.to_dicts()
        else:
            iocs = iocs_df

        return iocs

    def on_mount(self) -> None:
        """Provides a loop after generating the app for updating the data."""
        self.set_interval(1, self.update_iocs)

    async def update_iocs(self) -> None:
        """Updates the IOC stats data."""
        # Fetch services dataframe
        self._get_iocs()

        await self.populate_table()

    def _get_heading(self, column_id: str):
        sorted_style = Style(bold=True, underline=True)

        if column_id == self.sort_column_id:
            heading = Text(column_id, justify="center", style=sorted_style)
        else:
            heading = Text(column_id, justify="center").on(
                click=f"screen.sort('{column_id}')"
            )

        return heading

    def compose(self) -> ComposeResult:
        table: DataTable[Text] = DataTable(
            id="body_table", header_height=1, show_cursor=False, zebra_stripes=True
        )
        table.focus()

        for column_id in self.columns:
            heading = self._get_heading(column_id)
            table.add_column(heading, key=str(column_id))

        # Set a size for the left column
        # table.ordered_columns[0].content_width = 50

        table.show_cursor = True
        table.cursor_type = "row"

        yield table

    def watch_sort_column_id(self, sort_column_id: str) -> None:
        """Called when the sort_column_id attribute changes."""
        table = self.query_one("#body_table", DataTable)

        # Reformat headings based on new sorted column
        for i, _column in enumerate(self.columns):
            table.ordered_columns[i].label = self._get_heading(_column)

        sorted_col = self.columns.index(sort_column_id)

        table.sort(table.ordered_columns[sorted_col].key, reverse=False)

    def _get_color(self, value: str) -> Color:
        if value == "True":
            return Color.parse("lime")
        elif value == "False":
            return Color.parse("red")
        else:
            return Color.parse("white")

    async def populate_table(self) -> None:
        """Method to render the TUI table."""
        table = self.query_one("#body_table", DataTable)

        if not table.columns:
            return

        iocs = set(table.rows)
        new_iocs = set()

        # For each IOC row
        for ioc in self.iocs:
            row_key = str(ioc["name"])
            new_iocs.add(RowKey(row_key))

            cells = [
                {
                    "col_key": key,
                    "contents": SortableText(
                        ioc[key], str(ioc[key]), self._get_color(str(ioc[key]))
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
        for old_row_key in iocs - new_iocs:
            table.remove_row(old_row_key)

        # Sort by column
        table.sort(self.sort_column_id, reverse=False)


class MonitorApp(App):
    def __init__(
        self,
        beamline: str,
        commands: Commands,
        all: bool,
    ) -> None:
        super().__init__()

        self.commands = commands
        self.all = all
        self.beamline = beamline

    CSS_PATH = "monitor.tcss"

    BINDINGS = [
        Binding("escape", "close_application", "Exit"),
        Binding("s", "start_ioc", "Start IOC"),
        Binding("t", "stop_ioc", "Stop IOC"),
        Binding("r", "restart_ioc", "Restart IOC"),
        Binding("n", "sort('name')", "Sort: Name"),
        Binding("v", "sort('version')", "Sort: Version"),
        Binding("u", "sort('running')", "Sort: Running"),
        Binding("e", "sort('restarts')", "Sort: Restarts"),
        # Binding("d", "toggle_dark", "Toggle dark mode"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        self.table = IocTable(self.commands, self.all)
        yield self.table
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"{self.beamline} IOC Monitor"

    # def action_toggle_dark(self) -> None:
    #     """An action to toggle dark mode."""
    #     self.dark = not self.dark

    def action_close_application(self) -> None:
        """Provide another way of exiting the app along with CTRL+C."""
        self.table.stop()
        self.exit()


    def _get_service_name(self) -> str:
        table = self.get_widget_by_id("body_table")

        assert isinstance(table, DataTable)
        # Fetches hightlighted row ID (integer)
        row = table.cursor_row
        ioc_row = table.ordered_rows[row]
        ioc_col = table.ordered_columns[0]
        service_name = table.get_cell(ioc_row.key, ioc_col.key)

        return service_name

    def action_start_ioc(self) -> None:
        """Start the IOC that is currently highlighted."""
        service_name = self._get_service_name()

        def check_start(restart: bool) -> None:
            """Called when StartScreen is dismissed."""
            if restart:
                self.commands.start(service_name)

        self.push_screen(StartScreen(service_name), check_start)

    def action_stop_ioc(self) -> None:
        """Stop the IOC that is currently highlighted."""
        service_name = self._get_service_name()

        def check_stop(restart: bool) -> None:
            """Called when StopScreen is dismissed."""
            if restart:
                self.commands.stop(service_name)

        self.push_screen(StopScreen(service_name), check_stop)

    def action_restart_ioc(self) -> None:
        """Restart the IOC that is currently highlighted."""
        service_name = self._get_service_name()

        def check_restart(restart: bool) -> None:
            """Called when RestartScreen is dismissed."""
            if restart:
                self.commands.restart(service_name)

        self.push_screen(RestartScreen(service_name), check_restart)

    def action_sort(self, col_name: str) -> None:
        """An action to sort the table rows based on a given column attribute."""
        self.update_sort_key(col_name)

    def update_sort_key(self, col_name: str) -> None:
        """Method called to update the table sort key attribute."""
        table = self.query_one(IocTable)
        table.sort_column_id = col_name
