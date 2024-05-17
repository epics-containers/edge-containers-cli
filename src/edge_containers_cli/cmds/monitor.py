"""TUI monitor for containerised IOCs."""

from functools import total_ordering
from typing import Any, Callable, Union, cast

import polars
from rich.style import Style
from rich.text import Text

# from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header
from textual.widgets.data_table import RowKey

# @on(Button.Pressed, "#startstop")
# def startstop(self, event: Button.Pressed) -> None:
#     """Event handler called when a button is pressed."""
#     pass

# @on(Button.Pressed, "#logs")
# def logs(self, event: Button.Pressed) -> None:
#     """Event handler called when a button is pressed."""
#     pass


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

    def __init__(self, gs, all) -> None:
        super().__init__()

        self.get_services = gs
        self.all = all

        self._get_iocs()

    def _get_iocs(self) -> None:
        iocs_df = self.get_services(self.all)
        self.iocs = self._convert_df_to_list(iocs_df)
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
        self.set_interval(0.1, self.update_iocs)

    async def update_iocs(self) -> None:
        """Updates the IOC stats data."""
        # Fetch services dataframe
        self._get_iocs()

        await self.populate_table()

    def compose(self) -> ComposeResult:
        table: DataTable[Text] = DataTable(
            id="body_table", header_height=1, show_cursor=False, zebra_stripes=True
        )
        table.focus()
        for column_id in self.columns:
            heading = Text(column_id, justify="center")
            table.add_column(heading, key=str(column_id))

        # Set a size for the left column
        # table.ordered_columns[0].content_width = 50

        table.show_cursor = True
        table.cursor_type = "row"

        yield table

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

        # Sort in alphabetical order using NAME column
        table.sort("name", reverse=False)


class MonitorApp(App):
    def __init__(
        self,
        gs: Callable[[bool], Union[polars.DataFrame, list]],
        all: bool,
        beamline: str = "BL01T",
    ) -> None:
        super().__init__()

        self.get_services = gs
        self.all = all
        self.beamline = beamline

    CSS_PATH = "monitor.tcss"

    BINDINGS = [
        Binding("escape", "close_application", "Close Application"),
        Binding("up", "scroll_grid('up')", "Scroll Up"),
        Binding("down", "scroll_grid('down')", "Scroll Down"),
        # Binding("d", "toggle_dark", "Toggle dark mode"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        yield IocTable(self.get_services, self.all)
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"{self.beamline} IOC Monitor"

    # def action_toggle_dark(self) -> None:
    #     """An action to toggle dark mode."""
    #     self.dark = not self.dark

    def action_close_application(self) -> None:
        """Provide another way of exiting the app along with CTRL+C."""
        self.exit()

    def action_scroll_grid(self, direction: str) -> None:
        """Toggle pause on keypress"""
        table = self.query_one(DataTable)
        getattr(table, f"action_scroll_{direction}")()
