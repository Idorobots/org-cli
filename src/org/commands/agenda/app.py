"""Textual app for the interactive agenda command."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from org.cli_common import resolve_input_paths
from org.commands.tasks.common import (
    clock_duration_prompt_label,
    configured_capture_template_names,
)

from . import actions, ui
from .actions import AgendaSession, create_agenda_session


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import ClassVar

    from org_parser.document import Heading
    from textual.app import ComposeResult
    from textual.events import MouseScrollDown, MouseScrollUp, Resize
    from textual.widget import Widget

    from .command import AgendaArgs
    from .views import AgendaViewContext


_HELP_FOOTER_TEXT = "Type ? for help"


class AgendaRowWidget(Static):
    """One reusable rendered line in the agenda viewport."""

    def set_row(self, row_text: Text) -> None:
        """Update the widget content for one viewport row."""
        self.update(row_text)


class AgendaViewport(Vertical):
    """Virtualized agenda viewport backed by a reusable row widget pool."""

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        widget_id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Track row widgets explicitly so pool updates stay synchronous."""
        super().__init__(
            *children,
            name=name,
            id=widget_id,
            classes=classes,
            disabled=disabled,
        )
        self._row_widgets: list[AgendaRowWidget] = []

    def ensure_row_pool(self, count: int) -> None:
        """Grow or shrink the rendered row pool to match the viewport height."""
        missing = count - len(self._row_widgets)
        for _ in range(max(0, missing)):
            widget = AgendaRowWidget(classes="agenda-row")
            self._row_widgets.append(widget)
            self.mount(widget)
        while len(self._row_widgets) > count:
            self._row_widgets.pop().remove()

    def row_widgets(self) -> list[AgendaRowWidget]:
        """Return row widgets in display order."""
        return self._row_widgets


class AgendaApp(org.tui.app.CommandApp):
    """Textual app that backs interactive `agenda`."""

    CSS_PATH = "styles/app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("n", "move_down", show=False),
        Binding("p", "move_up", show=False),
        Binding("left", "page_backward", show=False),
        Binding("right", "page_forward", show=False),
        Binding("f", "page_forward", show=False),
        Binding("b", "page_backward", show=False),
        Binding("enter", "edit_selected", show=False),
        Binding("slash", "prompt_search", show=False),
        Binding("x", "clear_search", show=False),
        Binding("a", "prompt_capture", show=False),
        Binding("dollar_sign", "archive_selected", show=False),
        Binding("t", "prompt_state", show=False),
        Binding("r", "prompt_refile", show=False),
        Binding("c", "prompt_clock", show=False),
        Binding("shift+left", "shift_date_backward", show=False),
        Binding("shift+right", "shift_date_forward", show=False),
        Binding("shift+up", "shift_time_backward", show=False),
        Binding("shift+down", "shift_time_forward", show=False),
        Binding("question_mark", "show_help", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def __init__(self, session: AgendaSession) -> None:
        """Store the prepared agenda session."""
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        """Build the main agenda screen ui."""
        yield Vertical(
            Static(id="agenda-header"),
            Static(id="agenda-header-rule"),
            AgendaViewport(widget_id="agenda-body"),
            Static(id="agenda-footer-rule"),
            Static(id="agenda-footer"),
            Static(id="agenda-status"),
        )

    def on_mount(self) -> None:
        """Render initial state and arm the minute-refresh timer."""
        self.set_interval(1.0, self._refresh_for_clock_tick)
        self._refresh_view()

    def on_resize(self, _event: Resize) -> None:
        """Refresh viewport ui after terminal resize."""
        self._refresh_view()

    def on_mouse_scroll_up(self, _event: MouseScrollUp) -> None:
        """Match legacy wheel-up navigation behavior."""
        actions.move_selection(self.session, -1)
        self._refresh_view()

    def on_mouse_scroll_down(self, _event: MouseScrollDown) -> None:
        """Match legacy wheel-down navigation behavior."""
        actions.move_selection(self.session, 1)
        self._refresh_view()

    def _header_widget(self) -> Static:
        return self.query_one("#agenda-header", Static)

    def _body_widget(self) -> AgendaViewport:
        return self.query_one("#agenda-body", AgendaViewport)

    def _header_rule_widget(self) -> Static:
        return self.query_one("#agenda-header-rule", Static)

    def _footer_widget(self) -> Static:
        return self.query_one("#agenda-footer", Static)

    def _footer_rule_widget(self) -> Static:
        return self.query_one("#agenda-footer-rule", Static)

    def _status_widget(self) -> Static:
        return self.query_one("#agenda-status", Static)

    def _viewport_height(self) -> int:
        body_height = self._body_widget().size.height
        if body_height <= 0:
            return max(3, self.size.height - 3)
        return max(3, body_height)

    def _line_width(self) -> int:
        body_width = self._body_widget().size.width
        if body_width <= 0:
            return max(40, self.size.width)
        return max(40, body_width)

    def _refresh_header(self) -> None:
        sticky = ui.sticky_day(self.session)
        self._header_widget().update(
            Text(
                sticky.strftime("%A %Y-%m-%d"),
                style="bold" if self.session.render.color_enabled else "",
                no_wrap=True,
                overflow="ellipsis",
            ),
        )

    def _refresh_footer(self, viewport_height: int) -> None:
        total_rows = max(len(self.session.interactive_rows), 1)
        end_line = min(
            self.session.scroll_offset + viewport_height,
            len(self.session.interactive_rows),
        )
        search_text = self.session.search_text or "-"
        footer_style = "dim" if self.session.render.color_enabled else ""
        self._header_rule_widget().update(Rule(style=footer_style))
        self._footer_rule_widget().update(Rule(style=footer_style))
        self._footer_widget().update(
            org.tui.footer.footer_renderable(
                f"Lines {end_line}/{total_rows} | Search: {search_text}",
                _HELP_FOOTER_TEXT,
                style=footer_style,
            ),
        )

    def _refresh_status(self) -> None:
        footer_style = "dim" if self.session.render.color_enabled else ""
        self._status_widget().update(
            Text(
                self.session.status_message or "",
                style=footer_style,
                no_wrap=True,
                overflow="ellipsis",
            ),
        )

    def _refresh_rows(self, viewport_height: int) -> None:
        body = self._body_widget()
        body.ensure_row_pool(viewport_height)
        ui.sync_scroll_offset(self.session, viewport_height)
        selected_location = ui.selected_row_location(self.session)
        line_width = self._line_width()
        window = self.session.interactive_rows[
            self.session.scroll_offset : self.session.scroll_offset + viewport_height
        ]

        for widget, row in zip(body.row_widgets(), window, strict=False):
            widget.set_row(
                ui.render_viewport_row_text(
                    row,
                    self.session.render,
                    self.session.column_widths,
                    line_width=line_width,
                    highlighted=row.location == selected_location,
                ),
            )

        for widget in body.row_widgets()[len(window) :]:
            widget.set_row(Text(""))

    def _refresh_view(self) -> None:
        viewport_height = self._viewport_height()
        self._refresh_header()
        self._refresh_rows(viewport_height)
        self._refresh_footer(viewport_height)
        self._refresh_status()

    def _refresh_for_clock_tick(self) -> None:
        if actions.refresh_session_if_minute_changed(self.session):
            self._refresh_view()

    def _set_status(self, status_message: str) -> None:
        self.session.status_message = status_message

    def _run_external(self, callback: Callable[[], None]) -> None:
        self.run_external_and_refresh(callback, refresh=self._refresh_view)

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

    def action_page_backward(self) -> None:
        """Move the visible agenda window backward by the current span."""
        actions.set_start_date_relative(self.session, day_delta=-self.session.days)
        self._refresh_view()

    def action_page_forward(self) -> None:
        """Move the visible agenda window forward by the current span."""
        actions.set_start_date_relative(self.session, day_delta=self.session.days)
        self._refresh_view()

    def action_edit_selected(self) -> None:
        """Open the selected task in the external editor."""
        self._run_external(lambda: actions.edit_selected_task_in_external_editor(self.session))

    def action_archive_selected(self) -> None:
        """Archive the selected task subtree."""
        actions.archive_selected_task(self.session)
        self._refresh_view()

    def action_clear_search(self) -> None:
        """Clear the active search filter."""
        actions.clear_search(self.session)
        self._refresh_view()

    def action_shift_date_backward(self) -> None:
        """Shift the selected planning date backward by one day."""
        actions.apply_shift_date(self.session, day_delta=-1)
        self._refresh_view()

    def action_shift_date_forward(self) -> None:
        """Shift the selected planning date forward by one day."""
        actions.apply_shift_date(self.session, day_delta=1)
        self._refresh_view()

    def action_shift_time_backward(self) -> None:
        """Shift the selected timed planning row backward by one hour."""
        actions.apply_shift_time(self.session, hour_delta=-1)
        self._refresh_view()

    def action_shift_time_forward(self) -> None:
        """Shift the selected timed planning row forward by one hour."""
        actions.apply_shift_time(self.session, hour_delta=1)
        self._refresh_view()

    def action_show_help(self) -> None:
        """Open the key bindings help modal."""
        self.push_screen(
            org.tui.help.HelpModalScreen(
                ui.AGENDA_HELP_ENTRIES,
                color_enabled=self.session.render.color_enabled,
            ),
        )

    def action_prompt_search(self) -> None:
        """Open the search prompt with live filtering preview."""
        previous_text = self.session.search_text
        self._search_cancel_text = previous_text

        def _preview(value: str) -> None:
            actions.apply_search_text(self.session, value.strip())
            self._refresh_view()

        self._open_prompt(
            "Search text (blank clears)",
            initial_value=previous_text,
            on_change=_preview,
            on_submit=lambda value: actions.apply_search_text(self.session, value.strip()),
            on_cancel=lambda: self._cancel_search(previous_text),
        )

    def _cancel_search(self, previous_text: str) -> None:
        actions.apply_search_text(self.session, previous_text)
        self.session.status_message = "Search cancelled"

    def action_prompt_capture(self) -> None:
        """Prompt for a capture template and create a task."""
        status_message = actions.can_activate_agenda_capture_prompt(self.session)
        if status_message is not None:
            self._set_status(status_message)
            self._refresh_view()
            return

        template_names = configured_capture_template_names()

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
        status_message = actions.can_activate_agenda_state_prompt(self.session)
        if status_message is not None:
            self._set_status(status_message)
            self._refresh_view()
            return
        states = actions.state_choices_for_selected_row(self.session)

        self._open_selection(
            "TODO state",
            [org.tui.selection.SelectionOption(value=state, label=state) for state in states],
            on_submit=lambda selected_state: actions.apply_state_change_with_value(
                self.session,
                selected_state,
            ),
            on_cancel=lambda: self._set_status("State change cancelled"),
        )

    def action_prompt_refile(self) -> None:
        """Prompt for a destination file and refile the selected task."""
        if actions.selected_task_row(self.session) is None:
            self._set_status("Action available only on task rows")
            self._refresh_view()
            return

        self._open_selection(
            "Destination file",
            [
                org.tui.selection.SelectionOption(value=path, label=path)
                for path in resolve_input_paths(self.session.args.files)
            ],
            on_submit=lambda destination_path: actions.apply_refile_with_value(
                self.session,
                destination_path,
            ),
            on_cancel=lambda: self._set_status("Refile cancelled"),
        )

    def action_prompt_clock(self) -> None:
        """Prompt for a clock duration and append the clock entry."""
        if actions.selected_task_row(self.session) is None:
            self._set_status("Action available only on task rows")
            self._refresh_view()
            return

        self._open_prompt(
            clock_duration_prompt_label(),
            on_submit=lambda value: actions.apply_clock_entry_with_value(
                self.session,
                value.strip(),
            ),
            on_cancel=lambda: self._set_status("Clock action cancelled"),
        )

    def action_quit_app(self) -> None:
        """Exit the interactive agenda app."""
        self.exit()


def run_agenda_app(
    args: AgendaArgs,
    nodes: list[Heading],
    render: ui.RenderContext,
    view_ctx: AgendaViewContext,
) -> None:
    """Run the Textual-backed interactive agenda app."""
    session = create_agenda_session(args, nodes, render, view_ctx)
    AgendaApp(session).run()
