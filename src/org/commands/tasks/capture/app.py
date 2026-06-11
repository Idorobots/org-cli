"""Interactive Textual apps for tasks capture."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.text import Text
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static, TextArea

import org.tui.app
import org.tui.help
import org.tui.selection

from .domain import (
    _CAPTURE_HELP_ENTRIES,
    CapturePlan,
    _build_template_body,
)


if TYPE_CHECKING:
    from typing import ClassVar

    from textual import events as textual_events
    from textual.app import ComposeResult


class _TemplateSelectionApp(org.tui.app.CommandApp):
    """Small app for selecting a capture template interactively."""

    CSS_PATH = "styles/selection.tcss"

    def __init__(self, template_names: list[str]) -> None:
        super().__init__()
        self._template_names = template_names
        self.selected_template_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            Static(Text("Capture template", style="bold"), id="selection-title"),
            id="selection-root",
        )

    def on_mount(self) -> None:
        self._prompt_template_selection()

    def _prompt_template_selection(self) -> None:
        self.push_screen(
            org.tui.selection.SelectionModalScreen(
                "Capture template",
                [
                    org.tui.selection.SelectionOption(value=name, label=name)
                    for name in self._template_names
                ],
            ),
            callback=self._complete_template_selection,
        )

    def _complete_template_selection(self, value: str | None) -> None:
        """Exit after one shared selection modal result."""
        self.selected_template_name = value
        self.exit()


class CaptureApp(org.tui.app.CommandApp):
    """Interactive multi-field capture form with preview."""

    CSS_PATH = "styles/app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "save_capture", show=False, priority=True),
        Binding("escape", "cancel_capture", show=False, priority=True),
        Binding("question_mark", "show_help", show=False, priority=True),
    ]

    def __init__(self, plan: CapturePlan) -> None:
        """Store prepared capture plan and mutable field values."""
        super().__init__()
        self.plan = plan
        self.field_values = {
            placeholder: plan.values.get(placeholder, "") for placeholder in plan.placeholders
        }
        self.result_values: dict[str, str] | None = None
        self.status_message = ""

    def compose(self) -> ComposeResult:
        """Build the interactive capture form and preview layout."""
        yield Vertical(
            Static(Text(f"Template: {self.plan.template_name}", style="bold"), id="capture-title"),
            Horizontal(
                Vertical(
                    Static(Text("Preview", style="bold"), id="preview-title"),
                    Static(id="capture-preview"),
                    id="capture-preview-panel",
                ),
                Vertical(
                    Static(Text("Fields", style="bold"), id="fields-title"),
                    Vertical(id="capture-fields"),
                    Horizontal(
                        Button("Save", id="capture-save"),
                        Button("Cancel", id="capture-cancel"),
                        id="capture-buttons",
                    ),
                    id="capture-form",
                ),
                id="capture-body",
            ),
            Static(id="capture-status"),
        )

    def on_mount(self) -> None:
        """Mount unresolved placeholder inputs and focus the first field."""
        fields = self.query_one("#capture-fields", Vertical)
        for placeholder in self.plan.unresolved_placeholders:
            fields.mount(
                Static(
                    Text(f"Value for '{placeholder}'", style="bold"),
                    classes="field-label",
                ),
            )
            fields.mount(
                TextArea(
                    self.field_values[placeholder],
                    id=f"field-{placeholder}",
                    classes="field-input",
                    soft_wrap=True,
                    compact=True,
                ),
            )
        if self.plan.unresolved_placeholders:
            self.query_one(f"#field-{self.plan.unresolved_placeholders[0]}", TextArea).focus()
        self._refresh_view()

    def _preview_values(self) -> dict[str, str]:
        return {**self.plan.values, **self.field_values}

    def _refresh_view(self) -> None:
        preview = _build_template_body(
            self.plan.template_content,
            self._preview_values(),
            None,
            "",
        )
        self.query_one("#capture-preview", Static).update(Group(preview))
        self.query_one("#capture-status", Static).update(Text(self.status_message, style="dim"))

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Keep preview in sync with edited field values."""
        widget_id = event.text_area.id or ""
        if not widget_id.startswith("field-"):
            return
        placeholder = widget_id.removeprefix("field-")
        self.field_values[placeholder] = event.text_area.text
        self._refresh_view()

    def on_key(self, event: textual_events.Key) -> None:
        """Handle global capture keys even while inputs are focused."""
        key = event.key
        character = event.character or ""
        handler = None
        if key in {"question_mark", "?"} or character == "?":
            handler = self.action_show_help
        elif key == "ctrl+s":
            handler = self.action_save_capture
        elif key == "escape":
            handler = self.action_cancel_capture
        if handler is None:
            return
        event.stop()
        handler()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle save/cancel button presses."""
        if event.button.id == "capture-save":
            self.action_save_capture()
        elif event.button.id == "capture-cancel":
            self.action_cancel_capture()

    def action_show_help(self) -> None:
        """Open the key bindings help modal."""
        self.push_screen(org.tui.help.HelpModalScreen(_CAPTURE_HELP_ENTRIES, color_enabled=True))

    def action_cancel_capture(self) -> None:
        """Cancel interactive capture without saving."""
        self.result_values = None
        self.exit()

    def action_save_capture(self) -> None:
        """Save the current field values and exit the form."""
        self.result_values = self._preview_values()
        self.exit()


def run_template_selection_app(template_names: list[str]) -> str | None:
    """Run the template selection app and return the selected template name."""
    app = _TemplateSelectionApp(template_names)
    app.run()
    return app.selected_template_name


def run_capture_form_app(plan: CapturePlan) -> dict[str, str] | None:
    """Run the capture form app and return resolved field values."""
    app = CaptureApp(plan)
    app.run()
    return app.result_values
