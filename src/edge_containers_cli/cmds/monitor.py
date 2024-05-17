"""TUI monitor for containerised IOCs."""

from typing import Callable, Union

import polars
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    Static,
)


class Ioc(Static):
    def __init__(self, ioc, num):
        super().__init__(id=f"{ioc['name']}-{num}")

        self.ioc = ioc

    def compose(self) -> ComposeResult:
        with Container(id="iocs"):
            for key in self.ioc:
                yield TextDisplay(str(self.ioc[key]), key)
            yield Button("Start/Stop", id="startstop")
            yield Button("Logs", id="logs")

    @on(Button.Pressed, "#startstop")
    def startstop(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        pass

    @on(Button.Pressed, "#logs")
    def logs(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        pass


class UpdateLabel(Label):
    def __init__(self, text: str, id: str) -> None:
        super().__init__(id=id)

        self.text = reactive(text)


class TextDisplay(Label):
    def __init__(self, text: str, id: str) -> None:
        super().__init__(id=id)

        self.text = text

        assert isinstance(self.text, str)
        self.td = UpdateLabel(text=self.text, id="td")

    def compose(self) -> ComposeResult:
        yield self.td


class HeadingDisplay(Label):
    def __init__(self, text):
        super().__init__()

        self.text = text

    def compose(self) -> ComposeResult:
        td = Label(self.text, id="hd")
        yield td


class MonitorApp(App):
    def __init__(
        self, gs: Callable[[bool], Union[polars.DataFrame, list]], all: bool
    ) -> None:
        super().__init__()

        self.get_services = gs
        self.all = all

        iocs_df = self.get_services(self.all)
        self.iocs = self._convert_df_to_list(iocs_df)
        self.headings = self.iocs[0].keys()

        self.header = Header(show_clock=True)
        self.footer = Footer()

    CSS_PATH = "monitor.tcss"

    BINDINGS = [
        ("escape", "close_application", "Close Application"),
        ("d", "toggle_dark", "Toggle dark mode"),
    ]

    def _convert_df_to_list(self, iocs_df: Union[polars.DataFrame, list]) -> list:
        if isinstance(iocs_df, polars.DataFrame):
            iocs = iocs_df.to_dicts()
        else:
            iocs = iocs_df

        return iocs

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield self.header
        yield self.footer
        with Container(id="headings"):
            for heading in self.headings:
                h = HeadingDisplay(heading)
                h.styles.border = ("vkey", "black")
                yield h
        with ScrollableContainer():
            for i, row in enumerate(self.iocs):
                yield Ioc(row, i)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_close_application(self) -> None:
        """Provide another way of exiting the app along with CTRL+C."""
        self.exit()

    def on_mount(self) -> None:
        """Provides a loop after generating the app for updating the data."""
        self.set_interval(0.1, self.update_iocs)

    async def update_iocs(self) -> None:
        """Updates the IOC stats data."""
        # Fetch services dataframe
        iocs = self.get_services(self.all)  # type: ignore
        iocs = self._convert_df_to_list(iocs)

        # Loop over every IOC in the dataframe
        for i, ioc in enumerate(iocs):
            assert isinstance(ioc, dict)
            # This horrific logic is to find the correct widget...
            ioc_con = self.get_widget_by_id(f"{ioc['name']}-{i}").get_child_by_id(
                "iocs"
            )
            for key, val in ioc.items():
                # Once found, update with the new string
                textdisplay = ioc_con.get_child_by_id(key).get_child_by_id("td")
                assert isinstance(textdisplay, Label)
                textdisplay.update(str(val))
