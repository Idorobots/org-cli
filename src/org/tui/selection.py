"""Selection modal helpers for interactive Textual UIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.text import Text
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static


if TYPE_CHECKING:
    from textual import events as textual_events
    from textual.app import ComposeResult


@dataclass(frozen=True)
class SelectionOption:
    """One selectable value shown by the shared selection modal."""

    value: str
    label: str


class SelectionModalScreen(ModalScreen[str | None]):
    """Generic modal screen for keyboard-only single-value selection."""

    CSS_PATH = "styles/selection_modal.tcss"

    def __init__(
        self,
        label: str,
        options: list[SelectionOption],
        *,
        initial_index: int = 0,
    ) -> None:
        """Store modal selection configuration."""
        super().__init__()
        self._label = label
        self._options = options
        self._initial_index = initial_index

    def compose(self) -> ComposeResult:
        """Render the selection label and option list."""
        yield Container(
            Static(Text(self._label, style="bold"), id="selection-label"),
            Static(
                Text("Up/down moves. Enter selects. Esc cancels.", style="dim"),
                id="selection-instructions",
            ),
            OptionList(*(option.label for option in self._options), id="selection-options"),
            id="selection-dialog",
        )

    def on_mount(self) -> None:
        """Focus the selection list after the modal is mounted."""
        option_list = self.query_one(OptionList)
        if self._options:
            option_list.highlighted = min(max(self._initial_index, 0), len(self._options) - 1)
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Return the selected option value to the caller."""
        event.stop()
        self.dismiss(self._options[event.option_index].value)

    def on_key(self, event: textual_events.Key) -> None:
        """Consume escape so selection cancel doesn't fall through to app bindings."""
        if event.key != "escape":
            return
        event.stop()
        self.dismiss(None)
