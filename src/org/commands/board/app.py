"""Textual app for the interactive board command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.align import Align
from rich.console import Group, RenderableType
from rich.rule import Rule
from rich.text import Text
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from org.commands import runtime
from org.commands.tasks.common import (
    capture_template_prompt_label,
    configured_capture_template_names,
    resolve_capture_template_selection,
)

from . import events, layout
from .events import BoardSession, create_flow_board_session


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import ClassVar

    from org_parser.document import Heading
    from textual.app import ComposeResult
    from textual.events import MouseScrollDown, MouseScrollUp, Resize
    from textual.widget import Widget

    from .command import BoardArgs


_HELP_FOOTER_TEXT = "Type ? for help"


class BoardColumnWidget(Static):
    """One interactive board column with title and visible card slice."""

    def set_column(
        self,
        title: str,
        body: RenderableType,
        *,
        selected: bool,
    ) -> None:
        """Update the column title and rendered card group."""
        title_text = layout.render_column_title_text(title)
        title_text.no_wrap = True
        title_text.overflow = "ellipsis"
        if selected:
            title_text.stylize("reverse")
        self.update(Group(Align.center(title_text), body))


class BoardViewport(Horizontal):
    """Horizontal board viewport that owns one widget per visible column."""

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        widget_id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Track column widgets explicitly so pool updates stay synchronous."""
        super().__init__(
            *children,
            name=name,
            id=widget_id,
            classes=classes,
            disabled=disabled,
        )
        self._column_widgets: list[BoardColumnWidget] = []

    def ensure_column_pool(self, count: int) -> None:
        """Grow or shrink the rendered column pool to match the board state."""
        missing = count - len(self._column_widgets)
        for _ in range(max(0, missing)):
            widget = BoardColumnWidget(classes="board-column")
            self._column_widgets.append(widget)
            self.mount(widget)
        while len(self._column_widgets) > count:
            self._column_widgets.pop().remove()

    def column_widgets(self) -> list[BoardColumnWidget]:
        """Return board column widgets in display order."""
        return self._column_widgets


class BoardApp(runtime.CommandApp):
    """Textual app that backs interactive `board`."""

    CSS_PATH = "styles/app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("left", "move_left", show=False),
        Binding("right", "move_right", show=False),
        Binding("enter", "edit_selected", show=False),
        Binding("slash", "prompt_search", show=False),
        Binding("x", "clear_search", show=False),
        Binding("a", "prompt_capture", show=False),
        Binding("dollar_sign", "archive_selected", show=False),
        Binding("shift+left", "move_state_left", show=False),
        Binding("shift+right", "move_state_right", show=False),
        Binding("shift+up", "increase_priority", show=False),
        Binding("shift+down", "decrease_priority", show=False),
        Binding("question_mark", "show_help", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def __init__(self, session: BoardSession) -> None:
        """Store the prepared board session."""
        super().__init__()
        self.session = session
        self._visible_end_row = 0

    def compose(self) -> ComposeResult:
        """Build the main board app layout."""
        yield Vertical(
            BoardViewport(widget_id="board-body"),
            Static(id="board-footer-rule"),
            Static(id="board-footer"),
            Static(id="board-status"),
        )

    def on_mount(self) -> None:
        """Render initial state after mount."""
        self._refresh_view()

    def on_resize(self, _event: Resize) -> None:
        """Refresh viewport layout after terminal resize."""
        self._refresh_view()

    def on_mouse_scroll_up(self, _event: MouseScrollUp) -> None:
        """Match legacy wheel-up navigation behavior."""
        events.move_selection_vertical(self.session, -1)
        self._refresh_view()

    def on_mouse_scroll_down(self, _event: MouseScrollDown) -> None:
        """Match legacy wheel-down navigation behavior."""
        events.move_selection_vertical(self.session, 1)
        self._refresh_view()

    def _body_widget(self) -> BoardViewport:
        return self.query_one("#board-body", BoardViewport)

    def _footer_widget(self) -> Static:
        return self.query_one("#board-footer", Static)

    def _footer_rule_widget(self) -> Static:
        return self.query_one("#board-footer-rule", Static)

    def _status_widget(self) -> Static:
        return self.query_one("#board-status", Static)

    def _body_height(self) -> int:
        body_height = self._body_widget().size.height
        if body_height <= 0:
            return max(3, self.size.height - 2)
        return max(3, body_height - 1)

    def _body_width(self) -> int:
        body_width = self._body_widget().size.width
        if body_width <= 0:
            return max(80, self.size.width)
        return max(80, body_width)

    def _render_config(self) -> layout.BoardPanelRenderConfig:
        return layout.BoardPanelRenderConfig(
            width=layout.estimate_panel_content_width(
                self._body_width(),
                len(self.session.columns),
            ),
            color_enabled=self.session.color_enabled,
            done_states=self.session.done_states,
            todo_states=self.session.todo_states,
        )

    def _refresh_columns(self) -> None:
        body = self._body_widget()
        body.ensure_column_pool(len(self.session.columns))
        render = self._render_config()
        body_height = self._body_height()
        start_row, end_row = layout.selected_column_window(
            self.session,
            render,
            body_height=body_height,
        )
        self._visible_end_row = min(end_row, layout.selected_column_total_rows(self.session))

        for column_index, (widget, column) in enumerate(
            zip(body.column_widgets(), self.session.columns, strict=False),
        ):
            column_end = layout.column_window_end(
                column.nodes,
                render,
                start_row=start_row,
                body_height=body_height,
            )
            panels = [
                layout.build_task_panel(
                    node,
                    render,
                    highlighted=(
                        column_index == self.session.selected_column_index
                        and row_index == self.session.selected_row_index
                    ),
                )
                for row_index, node in enumerate(
                    column.nodes[start_row:column_end],
                    start=start_row,
                )
            ]
            renderable: RenderableType = Text("") if not panels else Group(*panels)
            widget.set_column(
                column.title,
                renderable,
                selected=column_index == self.session.selected_column_index,
            )

    def _refresh_footer(self) -> None:
        search_text = self.session.search_text or "-"
        total_rows = layout.selected_column_total_rows(self.session)
        footer_style = "dim" if self.session.color_enabled else ""
        self._footer_rule_widget().update(Rule(style=footer_style))
        self._footer_widget().update(
            runtime.footer_renderable(
                f"Rows {self._visible_end_row}/{total_rows} | Search: {search_text}",
                _HELP_FOOTER_TEXT,
                style=footer_style,
            ),
        )

    def _refresh_status(self) -> None:
        footer_style = "dim" if self.session.color_enabled else ""
        status = " ".join((self.session.status_message or "").splitlines())
        self._status_widget().update(
            Text(
                status,
                style=footer_style,
                no_wrap=True,
                overflow="ellipsis",
            ),
        )

    def _refresh_view(self) -> None:
        self._refresh_columns()
        self._refresh_footer()
        self._refresh_status()

    def _set_status(self, status_message: str) -> None:
        self.session.status_message = status_message

    def _run_external(self, callback: Callable[[], None]) -> None:
        self.suspend_for_external(callback)
        self._refresh_view()

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
            runtime.PromptModalScreen(label, initial_value=initial_value, on_change=on_change),
            callback=_complete,
        )

    def action_move_up(self) -> None:
        """Move the selection one task upward in the selected column."""
        events.move_selection_vertical(self.session, -1)
        self._refresh_view()

    def action_move_down(self) -> None:
        """Move the selection one task downward in the selected column."""
        events.move_selection_vertical(self.session, 1)
        self._refresh_view()

    def action_move_left(self) -> None:
        """Move board focus one non-empty column to the left."""
        events.move_selection_horizontal(self.session, -1)
        self._refresh_view()

    def action_move_right(self) -> None:
        """Move board focus one non-empty column to the right."""
        events.move_selection_horizontal(self.session, 1)
        self._refresh_view()

    def action_move_state_left(self) -> None:
        """Step the selected task state backward through document state order."""
        events.apply_state_move(self.session, direction=-1)
        self._refresh_view()

    def action_move_state_right(self) -> None:
        """Step the selected task state forward through document state order."""
        events.apply_state_move(self.session, direction=1)
        self._refresh_view()

    def action_increase_priority(self) -> None:
        """Increase the selected task priority."""
        events.apply_priority_shift(self.session, increase=True)
        self._refresh_view()

    def action_decrease_priority(self) -> None:
        """Decrease the selected task priority."""
        events.apply_priority_shift(self.session, increase=False)
        self._refresh_view()

    def action_edit_selected(self) -> None:
        """Open the selected task in the external editor."""
        self._run_external(lambda: events.edit_selected_task_in_external_editor(self.session))

    def action_archive_selected(self) -> None:
        """Archive the selected task subtree."""
        events.archive_selected_task(self.session)
        self._refresh_view()

    def action_clear_search(self) -> None:
        """Clear the active board search filter."""
        events.clear_search(self.session)
        self._refresh_view()

    def action_show_help(self) -> None:
        """Open the key bindings help modal."""
        self.push_screen(
            runtime.HelpModalScreen(
                layout.BOARD_HELP_ENTRIES,
                color_enabled=self.session.color_enabled,
            ),
        )

    def action_prompt_search(self) -> None:
        """Open the search prompt with live per-column filtering preview."""
        previous_text = self.session.search_text

        def _preview(value: str) -> None:
            events.apply_search_text(self.session, value.strip())
            self._refresh_view()

        self._open_prompt(
            "Search text (blank clears)",
            initial_value=previous_text,
            on_change=_preview,
            on_submit=lambda value: events.apply_search_text(self.session, value.strip()),
            on_cancel=lambda: self._cancel_search(previous_text),
        )

    def _cancel_search(self, previous_text: str) -> None:
        events.apply_search_text(self.session, previous_text)
        self.session.status_message = "Search cancelled"

    def action_prompt_capture(self) -> None:
        """Prompt for a capture template and create a task."""
        status_message = events.can_activate_capture_prompt(self.session)
        if status_message is not None:
            self._set_status(status_message)
            self._refresh_view()
            return

        template_names = configured_capture_template_names()

        def _submit(value: str) -> None:
            stripped = value.strip()
            if not stripped:
                self._set_status("Capture cancelled")
                return
            template_name = resolve_capture_template_selection(stripped, template_names)
            if template_name is None:
                self._set_status("Invalid capture template shortcut")
                self.action_prompt_capture()
                return
            self._run_external(lambda: events.apply_capture_task(self.session, template_name))

        self._open_prompt(
            capture_template_prompt_label(template_names),
            on_submit=_submit,
            on_cancel=lambda: self._set_status("Capture cancelled"),
        )

    def action_quit_app(self) -> None:
        """Exit the interactive board app."""
        self.exit()


def run_board_app(
    args: BoardArgs,
    nodes: list[Heading],
    todo_states: list[str],
    done_states: list[str],
    color_enabled: bool,
) -> None:
    """Run the Textual-backed interactive board app."""
    session = create_flow_board_session(args, nodes, todo_states, done_states, color_enabled)
    BoardApp(session).run()
