"""Prompt modal helpers for interactive Textual UIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Static


if TYPE_CHECKING:
    from collections.abc import Callable

    from textual import events as textual_events
    from textual.app import ComposeResult


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
