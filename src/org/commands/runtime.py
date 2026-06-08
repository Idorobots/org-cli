"""Shared Textual runtime helpers for interactive command UIs."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.table import Table
from rich.text import Text
from textual import events as textual_events
from textual.app import App, ComposeResult, SuspendNotSupported
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from org.commands.interactive_common import (
    InteractiveHelpEntry,
    render_interactive_help_panel_text,
)


if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager


def _help_body_text(entries: list[InteractiveHelpEntry]) -> Text:
    """Build help body text without duplicating the modal title."""
    panel_text = render_interactive_help_panel_text(entries)
    body_lines = panel_text.splitlines()[1:]
    return Text.from_markup("\n".join(body_lines))


def footer_renderable(left_text: str, right_text: str, *, style: str) -> Table:
    """Build one footer line with a right-aligned help hint."""
    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(left_text, style=style, no_wrap=True, overflow="ellipsis"),
        Text(right_text, style=style, no_wrap=True, overflow="ellipsis"),
    )
    return footer_line


class HelpModalScreen(ModalScreen[None]):
    """Generic modal screen that renders command key bindings."""

    CSS_PATH = "styles/help_modal.tcss"

    def __init__(self, entries: list[InteractiveHelpEntry], *, color_enabled: bool) -> None:
        """Store key binding data for modal rendering."""
        super().__init__()
        self._entries = entries
        self._color_enabled = color_enabled
        self._ready_to_close = False

    def compose(self) -> ComposeResult:
        """Render the help modal contents."""
        title_text = Text("Key bindings", style="bold")
        help_text = _help_body_text(self._entries)
        yield Container(
            Static(title_text, id="help-title"),
            Static(help_text, id="help-content"),
            id="help-dialog",
        )

    def on_mount(self) -> None:
        """Arm key-to-close after the opening key event finishes."""
        self.call_after_refresh(self._enable_close)

    def _enable_close(self) -> None:
        """Allow subsequent key presses to close the help modal."""
        self._ready_to_close = True

    async def on_key(self, event: textual_events.Key) -> None:
        """Close and forward the next key press to the underlying app."""
        event.stop()
        if not self._ready_to_close:
            return
        forwarded_event = textual_events.Key(event.key, event.character)
        self.dismiss(None)
        self.app.call_after_refresh(lambda: self.app.post_message(forwarded_event))


class PromptModalScreen(ModalScreen[str | None]):
    """Generic modal screen for single-value text prompts."""

    CSS_PATH = "styles/prompt_modal.tcss"

    def __init__(
        self,
        label: str,
        *,
        initial_value: str = "",
        on_change: Callable[[str], None] | None = None,
    ) -> None:
        """Store modal prompt configuration."""
        super().__init__()
        self._label = label
        self._initial_value = initial_value
        self._on_change = on_change

    def compose(self) -> ComposeResult:
        """Render the prompt label and input field."""
        yield Container(
            Static(Text(self._label, style="bold"), id="prompt-label"),
            Static(Text("Enter submits. Esc cancels.", style="dim"), id="prompt-instructions"),
            Input(value=self._initial_value, id="prompt-input"),
            id="prompt-dialog",
        )

    def on_mount(self) -> None:
        """Focus the prompt input after the modal is mounted."""
        self.query_one(Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Forward value changes to optional preview callback."""
        if self._on_change is not None:
            self._on_change(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Return submitted input value to caller."""
        self.dismiss(event.value)

    def on_key(self, event: textual_events.Key) -> None:
        """Consume escape so prompt cancel doesn't fall through to app bindings."""
        if event.key != "escape":
            return
        event.stop()
        self.dismiss(None)


class CommandApp(App[None]):
    """Shared helpers for Textual-backed interactive command apps."""

    def suspend_for_external(self, callback: Callable[[], None]) -> None:
        """Suspend the app when possible around one blocking callback."""
        suspend = getattr(self, "suspend", None)
        if callable(suspend):
            try:
                with cast("AbstractContextManager[object]", suspend()):
                    callback()
            except SuspendNotSupported:
                callback()
        else:
            callback()

    def run_external_and_refresh(
        self,
        callback: Callable[[], None],
        *,
        refresh: Callable[[], None],
    ) -> None:
        """Suspend around one external action and refresh afterwards."""
        self.suspend_for_external(callback)
        refresh()
