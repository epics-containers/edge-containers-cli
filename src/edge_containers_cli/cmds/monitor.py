"""TUI monitor for containerised IOCs."""

from typing import Union

import polars

from textual.app import App, ComposeResult

from textual.containers import Container, ScrollableContainer

from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    Static,
)


class Ioc(Static):
    def __init__(self, ioc):
        super().__init__()

        self.ioc = ioc

    def compose(self) -> ComposeResult:
        with Container(id="iocs"):
            for key in self.ioc:
                yield TextDisplay(str(self.ioc[key]))
            yield Button("Start/Stop", id="startstop")
            yield Button("Logs", id="logs")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button_id = event.button.id
        if button_id == "startstop":
            pass
        elif button_id == "logs":
            pass
        pass


class TextDisplay(Label):
    def __init__(self, text):
        super().__init__()

        self.text = text

    def compose(self):
        td = Label(self.text, id="td")
        yield td


class HeadingDisplay(Label):
    def __init__(self, text):
        super().__init__()

        self.text = text

    def compose(self):
        td = Label(self.text, id="hd")
        yield td


class MonitorApp(App):
    def __init__(self, iocs_df: Union[polars.DataFrame, list]) -> None:
        super().__init__()

        if isinstance(iocs_df, polars.DataFrame):
            self.iocs = iocs_df.to_dicts()
            self.headings = self.iocs[0].keys()
        else:
            self.iocs = iocs_df

        self.header = Header(show_clock=True)
        self.footer = Footer()

    CSS_PATH = "monitor.tcss"

    BINDINGS = [
        ("#", "close_application", "Close Application"),
        ("d", "toggle_dark", "Toggle dark mode"),
    ]

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
            for row in self.iocs:
                yield Ioc(row)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_close_application(self) -> None:
        """Provide another way of exiting the app along with CTRL+C."""
        self.exit()


# if __name__ == "__main__":
#     app = MonitorApp()
#     app.run()
