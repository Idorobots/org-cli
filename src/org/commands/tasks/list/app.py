"""Textual app for the interactive tasks list command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group, RenderableType
from rich.rule import Rule
from rich.text import Text
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Static

import org.tui.app
import org.tui.footer
import org.tui.help
import org.tui.prompt
import org.tui.selection
from org.commands.tasks.common import (
    PlanningTimestampField,
    configured_capture_template_names,
    planning_prompt_label,
    tags_prompt_label,
)
from org.tui.bits import TaskLineConfig, format_task_line

from . import actions
from .actions import TASKS_LIST_HELP_ENTRIES, create_tasks_list_session


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import ClassVar

    from org_parser.document import Heading
    from textual.app import ComposeResult
    from textual.events import MouseScrollDown, MouseScrollUp, Resize

    from .command import ListArgs, _TasksListSessionData


_HIGHLIGHT_ROW_STYLE = "on grey23"
_HELP_FOOTER_TEXT = "Type ? for help"


class TasksListApp(org.tui.app.CommandApp):
    """Textual app that backs interactive `tasks list`."""

    CSS_PATH = "styles/app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("n", "move_down", show=False),
        Binding("p", "move_up", show=False),
        Binding("shift+up", "increase_priority", show=False),
        Binding("shift+down", "decrease_priority", show=False),
        Binding("enter", "edit_selected", show=False),
        Binding("slash", "prompt_search", show=False),
        Binding("x", "clear_search", show=False),
        Binding("a", "prompt_capture", show=False),
        Binding("dollar_sign", "archive_selected", show=False),
        Binding("t", "prompt_state", show=False),
        Binding("g", "prompt_tags", show=False),
        Binding("s", "prompt_scheduled", show=False),
        Binding("d", "prompt_deadline", show=False),
        Binding("c", "prompt_closed", show=False),
        Binding("question_mark", "show_help", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def __init__(self, args: ListArgs, data: _TasksListSessionData) -> None:
        """Build one tasks list app from CLI args and loaded session data."""
        super().__init__()
        self.session = create_tasks_list_session(args, data)

    def compose(self) -> ComposeResult:
        """Build the main app layout."""
        yield Vertical(
            Static(id="tasks-body"),
            Static(id="tasks-footer-rule"),
            Static(id="tasks-footer"),
            Static(id="tasks-status"),
        )

    def on_mount(self) -> None:
        """Render initial state after mount."""
        self._refresh_view()

    def on_resize(self, _event: Resize) -> None:
        """Refresh viewport layout after terminal resize."""
        self._refresh_view()

    def on_mouse_scroll_up(self, _event: MouseScrollUp) -> None:
        """Match legacy wheel-up navigation behavior."""
        actions.move_selection(self.session, -1)
        self._refresh_view()

    def on_mouse_scroll_down(self, _event: MouseScrollDown) -> None:
        """Match legacy wheel-down navigation behavior."""
        actions.move_selection(self.session, 1)
        self._refresh_view()

    def _body_widget(self) -> Static:
        return self.query_one("#tasks-body", Static)

    def _footer_widget(self) -> Static:
        return self.query_one("#tasks-footer", Static)

    def _footer_rule_widget(self) -> Static:
        return self.query_one("#tasks-footer-rule", Static)

    def _status_widget(self) -> Static:
        return self.query_one("#tasks-status", Static)

    def _viewport_height(self) -> int:
        body_height = self._body_widget().size.height
        if body_height <= 0:
            return max(5, self.size.height - 2)
        return max(5, body_height)

    def _sync_scroll(self, viewport_height: int) -> None:
        max_offset = max(0, len(self.session.visible_nodes) - viewport_height)
        self.session.scroll_offset = min(max(self.session.scroll_offset, 0), max_offset)
        if not self.session.visible_nodes:
            return
        if self.session.selected_index < self.session.scroll_offset:
            self.session.scroll_offset = self.session.selected_index
        elif self.session.selected_index >= self.session.scroll_offset + viewport_height:
            self.session.scroll_offset = self.session.selected_index - viewport_height + 1
        self.session.scroll_offset = min(max(self.session.scroll_offset, 0), max_offset)

    def _row_text(self, node: Heading, *, line_width: int) -> Text:
        line = format_task_line(
            node,
            TaskLineConfig(
                color_enabled=self.session.color_enabled,
                done_states=self.session.done_states,
                todo_states=self.session.todo_states,
                line_width=line_width,
            ),
        )
        if self.session.color_enabled:
            return Text.from_markup(line)
        return Text(line)

    def _body_renderable(self) -> Group:
        viewport_height = self._viewport_height()
        actions.ensure_selection_bounds(self.session)
        self._sync_scroll(viewport_height)
        window = self.session.visible_nodes[
            self.session.scroll_offset : self.session.scroll_offset + viewport_height
        ]
        rows: list[Text] = []
        line_width = max(20, self.size.width - 1)
        for index, node in enumerate(window, start=self.session.scroll_offset):
            row = self._row_text(node, line_width=line_width)
            if index == self.session.selected_index:
                row.stylize(_HIGHLIGHT_ROW_STYLE)
            rows.append(row)
        rows.extend(Text("") for _ in range(viewport_height - len(window)))
        return Group(*rows)

    def _footer_renderable(self) -> RenderableType:
        selected_row = self.session.selected_index + 1 if self.session.visible_nodes else 0
        total_rows = len(self.session.visible_nodes)
        search_text = self.session.search_text or "-"
        footer_style = "dim" if self.session.color_enabled else ""
        return org.tui.footer.footer_renderable(
            f"Rows {selected_row}/{total_rows} | Search: {search_text}",
            _HELP_FOOTER_TEXT,
            style=footer_style,
        )

    def _status_renderable(self) -> Text:
        footer_style = "dim" if self.session.color_enabled else ""
        return Text(
            self.session.status_message or "",
            style=footer_style,
            no_wrap=True,
            overflow="ellipsis",
        )

    def _refresh_view(self) -> None:
        footer_style = "dim" if self.session.color_enabled else ""
        self._body_widget().update(self._body_renderable())
        self._footer_rule_widget().update(Rule(style=footer_style))
        self._footer_widget().update(self._footer_renderable())
        self._status_widget().update(self._status_renderable())

    def _open_prompt(
        self,
        label: str,
        *,
        initial_value: str = "",
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        def _complete(result: str | None) -> None:
            if result is None:
                on_cancel()
            else:
                on_submit(result)
            self._refresh_view()

        self.push_screen(
            org.tui.prompt.PromptModalScreen(
                label,
                initial_value=initial_value,
                on_change=on_change,
            ),
            callback=_complete,
        )

    def _run_external(self, callback: Callable[[], None]) -> None:
        self.run_external_and_refresh(callback, refresh=self._refresh_view)

    def _open_selection(
        self,
        label: str,
        options: list[org.tui.selection.SelectionOption],
        *,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        def _complete(result: str | None) -> None:
            if result is None:
                on_cancel()
            else:
                on_submit(result)
            self._refresh_view()

        self.push_screen(org.tui.selection.SelectionModalScreen(label, options), callback=_complete)

    def action_move_up(self) -> None:
        """Move the selection one row upward."""
        actions.move_selection(self.session, -1)
        self._refresh_view()

    def action_move_down(self) -> None:
        """Move the selection one row downward."""
        actions.move_selection(self.session, 1)
        self._refresh_view()

    def action_increase_priority(self) -> None:
        """Raise the selected task priority one step."""
        actions.apply_priority_shift(self.session, increase=True)
        self._refresh_view()

    def action_decrease_priority(self) -> None:
        """Lower the selected task priority one step."""
        actions.apply_priority_shift(self.session, increase=False)
        self._refresh_view()

    def action_clear_search(self) -> None:
        """Clear the active search filter."""
        actions.clear_search(self.session)
        self._refresh_view()

    def action_edit_selected(self) -> None:
        """Open the selected task in the external editor."""
        self._run_external(lambda: actions.edit_selected_task_in_external_editor(self.session))

    def action_archive_selected(self) -> None:
        """Archive the selected task subtree."""
        actions.archive_selected_task(self.session)
        self._refresh_view()

    def action_quit_app(self) -> None:
        """Exit the interactive tasks list app."""
        self.exit()

    def action_show_help(self) -> None:
        """Open the key bindings help modal."""
        self.push_screen(
            org.tui.help.HelpModalScreen(
                TASKS_LIST_HELP_ENTRIES,
                color_enabled=self.session.color_enabled,
            ),
        )

    def action_prompt_search(self) -> None:
        """Open the search prompt with live filtering preview."""
        previous_text = self.session.search_text

        def _preview(value: str) -> None:
            actions.apply_search_text(self.session, value.strip())
            self._refresh_view()

        self._open_prompt(
            "Search text (blank clears)",
            initial_value=self.session.search_text,
            on_change=_preview,
            on_submit=lambda value: actions.apply_search_text(self.session, value.strip()),
            on_cancel=lambda: self._cancel_search(previous_text),
        )

    def _cancel_search(self, previous_text: str) -> None:
        actions.apply_search_text(self.session, previous_text)
        self.session.status_message = "Search cancelled"

    def action_prompt_capture(self) -> None:
        """Prompt for a capture template and create a task."""
        template_names = configured_capture_template_names()
        if not template_names:
            self.session.status_message = "No capture templates configured"
            self._refresh_view()
            return

        self._open_selection(
            "Capture template",
            [org.tui.selection.SelectionOption(value=name, label=name) for name in template_names],
            on_submit=lambda template_name: self._run_external(
                lambda: actions.apply_capture_task(self.session, template_name),
            ),
            on_cancel=lambda: self._set_status("Capture cancelled"),
        )

    def action_prompt_state(self) -> None:
        """Prompt for a TODO state transition."""
        status_message = actions.can_activate_state_prompt(self.session)
        if status_message is not None:
            self.session.status_message = status_message
            self._refresh_view()
            return
        states = actions.state_choices_for_selected_node(self.session)

        self._open_selection(
            "TODO state",
            [org.tui.selection.SelectionOption(value=state, label=state) for state in states],
            on_submit=lambda selected_state: actions.apply_state_change_with_value(
                self.session,
                selected_state,
            ),
            on_cancel=lambda: self._set_status("State change cancelled"),
        )

    def action_prompt_tags(self) -> None:
        """Prompt for replacement tag CSV on the selected task."""
        self._open_prompt(
            tags_prompt_label(),
            on_submit=lambda value: actions.apply_tags_edit(self.session, value),
            on_cancel=lambda: self._set_status("Tags edit cancelled"),
        )

    def _set_status(self, status_message: str) -> None:
        self.session.status_message = status_message

    def _prompt_planning(self, field: PlanningTimestampField) -> None:
        self._open_prompt(
            planning_prompt_label(field),
            on_submit=lambda value: actions.apply_planning_timestamp_edit(
                self.session,
                field=field,
                raw_timestamp=value,
            ),
            on_cancel=lambda: self._set_status("Planning timestamp edit cancelled"),
        )

    def action_prompt_scheduled(self) -> None:
        """Prompt for a scheduled timestamp value."""
        self._prompt_planning("scheduled")

    def action_prompt_deadline(self) -> None:
        """Prompt for a deadline timestamp value."""
        self._prompt_planning("deadline")

    def action_prompt_closed(self) -> None:
        """Prompt for a closed timestamp value."""
        self._prompt_planning("closed")


def run_tasks_list_app(args: ListArgs, data: _TasksListSessionData) -> None:
    """Run the Textual-backed interactive tasks list app."""
    TasksListApp(args, data).run()
