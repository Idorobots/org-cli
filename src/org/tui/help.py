"""Help text and help modal helpers for interactive Textual UIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.markup import escape
from rich.text import Text
from textual import events as textual_events
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Static


if TYPE_CHECKING:
    from textual.app import ComposeResult


INTERACTIVE_HELP_CLI_NOTE = (
    "In interactive mode, press ? to open key bindings help (press any key to close)."
)


@dataclass(frozen=True)
class InteractiveHelpEntry:
    """One key binding entry for interactive help rendering."""

    key: str
    description: str


def render_interactive_help_panel_text(entries: list[InteractiveHelpEntry]) -> str:
    """Render key bindings as plain help text lines."""
    key_width = max(12, max((len(entry.key) for entry in entries), default=0) + 1)
    lines = ["[white not dim]Key bindings:[/]"]
    for entry in entries:
        key_text = escape(f"{entry.key:<{key_width}}")
        description_text = escape(entry.description)
        lines.append(f"  [bold white not dim]{key_text}[/][white not dim]{description_text}[/]")
    return "\n".join(lines)


def interactive_help_command_text(base_text: str, entries: list[InteractiveHelpEntry]) -> str:
    """Append the shared interactive-help note and key-bindings panel to help text."""
    normalized = " ".join(base_text.split())
    panel_text = render_interactive_help_panel_text(entries)
    return f"{normalized} {INTERACTIVE_HELP_CLI_NOTE}\n\n{panel_text}"


def _help_body_text(entries: list[InteractiveHelpEntry]) -> Text:
    """Build help body text without duplicating the modal title."""
    panel_text = render_interactive_help_panel_text(entries)
    body_lines = panel_text.splitlines()[1:]
    return Text.from_markup("\n".join(body_lines))


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
