"""Tests for board command."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from io import StringIO
from typing import TYPE_CHECKING, cast

import pytest
import typer
from rich.console import Console
from rich.text import Text

from org import config as config_module
from org.commands import archive as archive_command
from org.commands import board as board_command
from org.commands import editor as editor_command
from org.commands import interactive_actions
from org.commands.interactive_common import heading_identity
from org.commands.tasks import capture as capture_command
from tests.conftest import node_from_org


if TYPE_CHECKING:
    from collections.abc import Iterator

    from org_parser.document import Document, Heading
    from rich.live import Live


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def make_board_args(files: list[str], **overrides: object) -> board_command.BoardArgs:
    """Build BoardArgs with defaults and overrides."""
    args = board_command.BoardArgs(
        files=files,
        config=".org-cli.yaml",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_states="TODO",
        done_states="DONE",
        filter_priority=None,
        filter_level=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
        color_flag=False,
        view=None,
        width=120,
        max_results=None,
        offset=0,
        days=7,
        order_by_level=False,
        order_by_file_order=False,
        order_by_file_order_reversed=False,
        order_by_priority=False,
        order_by_timestamp_asc=False,
        order_by_timestamp_desc=False,
        with_tags_as_category=False,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def _visible_board_titles_by_column(
    session: board_command._BoardSession,
) -> dict[str, list[str]]:
    """Return visible task titles grouped by board column title."""
    return {column.title: [node.title_text for node in column.nodes] for column in session.columns}


def _pin_board_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin board command current time for deterministic completed-task windows."""
    monkeypatch.setattr(
        board_command,
        "local_now",
        lambda: datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
    )


def test_filter_recent_completed_nodes_uses_latest_timestamp_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed tasks should be filtered by latest_timestamp recency."""
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(board_command, "local_now", lambda: now)

    nodes = node_from_org(
        "* TODO Active task\n"
        "* DONE Recent done\n"
        "CLOSED: [2026-05-08 Fri 09:00]\n"
        "* DONE Old done\n"
        "CLOSED: [2026-04-01 Wed 09:00]\n",
    )

    filtered = board_command._filter_recent_completed_nodes(nodes, days=7)

    assert [node.title_text for node in filtered] == ["Active task", "Recent done"]


def test_filter_recent_completed_nodes_respects_days_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Days override should widen completed-task retention window."""
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(board_command, "local_now", lambda: now)

    nodes = node_from_org(
        "* DONE Mid-age done\nCLOSED: [2026-04-25 Sat 09:00]\n",
    )

    assert board_command._filter_recent_completed_nodes(nodes, days=7) == []
    assert [
        node.title_text for node in board_command._filter_recent_completed_nodes(nodes, days=30)
    ] == [
        "Mid-age done",
    ]


def test_run_flow_board_renders_expected_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should render built-in selector fallback columns."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        width=150,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "org",
            "board",
            "--todo-states",
            "TODO,WAITING,IN-PROGRESS",
            "--done-states",
            "DONE,CANCELLED,ARCHIVED",
            "--width",
            "150",
        ],
    )
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Backlog" in output
    assert "TODO" in output
    assert "DONE" in output


def test_run_flow_board_column_order_follows_document_todo_order(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Board fallback columns should keep Backlog/TODO/DONE order."""
    fixture_path = os.path.join(tmp_path, "ordered_states.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "#+TODO: BACKLOG NEXT ACTIVE | DONE CANCELLED\n"
            "* BACKLOG First\n"
            "* NEXT Second\n"
            "* ACTIVE Third\n"
            "* DONE Fourth\n",
        )

    args = make_board_args(
        [fixture_path],
        todo_states="TODO",
        done_states="DONE",
        width=220,
    )
    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "220"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    pos_not_started = output.find("Backlog")
    pos_todo = output.find("TODO")
    pos_done = output.find("DONE")

    assert pos_not_started != -1
    assert pos_todo != -1
    assert pos_done != -1
    assert pos_not_started < pos_todo
    assert pos_todo < pos_done


def test_run_flow_board_preserves_order_in_column_when_priorities_equal(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should keep stable per-column order when priorities are equal."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args(
        [fixture_path],
        width=120,
        order_by_file_order=True,
        days=100000,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--order-by-file-order"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    first = output.find("Refactor codebase")
    second = output.find("Fix bug in parser")
    assert first != -1
    assert second != -1
    assert first < second


def test_build_selector_board_columns_preserves_processed_order() -> None:
    """Selector lane content should preserve input processed order."""
    nodes = node_from_org(
        "* TODO [#C] Low\n* TODO Middle\n* TODO [#A] High\n* TODO [#B] Medium\n",
    )

    specs = board_command._resolve_column_specs(make_board_args([]))
    columns = board_command._build_selector_board_columns(nodes, specs)

    todo_column = next(column for column in columns if column.title == "TODO")
    assert [node.title_text for node in todo_column.nodes] == ["Low", "Middle", "High", "Medium"]


def test_build_selector_board_columns_with_order_by_overrides_processed_order() -> None:
    """Column order-by should apply sort_by selector after filtering."""
    nodes = node_from_org(
        "* TODO a\n* TODO c\n* TODO b\n",
    )
    view = config_module.BoardViewConfig(
        name="ordered",
        columns=[
            config_module.BoardColumnConfig(
                name="TODO",
                filter=".todo != null",
                order_by=".title_text",
            ),
        ],
    )

    columns = board_command._build_selector_board_columns(
        nodes,
        board_command._compile_view_column_specs(view),
    )

    todo_column = next(column for column in columns if column.title == "TODO")
    assert [node.title_text for node in todo_column.nodes] == ["c", "b", "a"]


def test_build_selector_board_columns_allows_matches_in_multiple_columns() -> None:
    """One task can appear in multiple selector columns."""
    nodes = node_from_org("* TODO Shared\n* DONE Finished\n")
    view = config_module.BoardViewConfig(
        name="overlap",
        columns=[
            config_module.BoardColumnConfig(name="Any todo", filter=".todo != null"),
            config_module.BoardColumnConfig(name="Open", filter="not(.is_completed)"),
        ],
    )

    columns = board_command._build_selector_board_columns(
        nodes,
        board_command._compile_view_column_specs(view),
    )

    any_todo_column = next(column for column in columns if column.title == "Any todo")
    open_column = next(column for column in columns if column.title == "Open")
    assert [node.title_text for node in any_todo_column.nodes] == ["Shared", "Finished"]
    assert [node.title_text for node in open_column.nodes] == ["Shared"]


def test_build_selector_board_columns_omits_non_matching_tasks() -> None:
    """Tasks that match no selectors should not appear in any column."""
    nodes = node_from_org("* TODO Open\n* DONE Closed\n")
    view = config_module.BoardViewConfig(
        name="nomatch",
        columns=[
            config_module.BoardColumnConfig(name="Backlog", filter=".todo == null"),
        ],
    )

    columns = board_command._build_selector_board_columns(
        nodes,
        board_command._compile_view_column_specs(view),
    )

    assert len(columns) == 1
    assert columns[0].title == "Backlog"
    assert columns[0].nodes == []


def test_render_column_title_text_allows_rich_markup() -> None:
    """Column titles should support Rich markup syntax."""
    title = board_command._render_column_title_text("[bold green]Complete[/]")

    assert title.plain == "Complete"
    assert title.spans


def test_render_column_title_text_falls_back_on_invalid_markup() -> None:
    """Invalid markup in column title should render as literal text."""
    title = board_command._render_column_title_text("[bold")

    assert title.plain == "[bold"


def test_move_selection_horizontal_skips_empty_columns() -> None:
    """Horizontal navigation should skip empty lanes."""
    args = make_board_args([])
    first, second = node_from_org("* TODO First\n* TODO Second\n")
    session = board_command._BoardSession(
        args=args,
        nodes=[first, second],
        todo_states=["TODO", "WAITING", "INPROGRESS"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", [first]),
            board_command._BoardColumn("WAITING", []),
            board_command._BoardColumn("INPROGRESS", [second]),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    assert session.selected_column_index == 1
    board_command._move_selection_horizontal(session, 1)
    assert session.selected_column_index == 3

    board_command._move_selection_horizontal(session, -1)
    assert session.selected_column_index == 1


def test_interactive_viewport_rows_scales_with_panel_height() -> None:
    """Interactive viewport should account for panel line height."""
    assert board_command._interactive_viewport_rows(24) == 4
    assert board_command._interactive_viewport_rows(13) == 2
    assert board_command._interactive_viewport_rows(9) == 1


def test_sync_scroll_for_selection_keeps_selected_row_visible() -> None:
    """Scroll sync should move viewport so selected task stays visible."""
    args = make_board_args([])
    nodes = node_from_org("\n".join(f"* TODO Task {index}" for index in range(6)))
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=4,
        scroll_offset=0,
        status_message="",
    )
    render = board_command._BoardPanelRenderConfig(
        width=30,
        color_enabled=False,
        done_states=["DONE"],
        todo_states=["TODO"],
    )
    row_heights = board_command._interactive_row_heights(session, render)
    _start, _end, _used = board_command._sync_scroll_for_selection(
        session,
        row_heights,
        available_lines=8,
    )

    assert session.scroll_offset == 3


def test_step_heading_state_right_from_none_uses_first_document_state() -> None:
    """Shift-right from empty state should use first all_states item."""
    heading = node_from_org("#+TODO: TODO WAITING | DONE\n* Task\n")[0]

    new_state, status = board_command._step_heading_state(heading, direction=1)

    assert new_state == "TODO"
    assert status is None


def test_step_heading_state_left_from_first_moves_to_none() -> None:
    """Shift-left from first state should clear todo state."""
    heading = node_from_org("#+TODO: TODO WAITING | DONE\n* TODO Task\n")[0]

    new_state, status = board_command._step_heading_state(heading, direction=-1)

    assert new_state is None
    assert status is None


def test_step_heading_state_moves_prev_next_in_middle() -> None:
    """Shift-left/right should move through middle states."""
    heading = node_from_org("#+TODO: TODO WAITING | DONE\n* WAITING Task\n")[0]

    next_state, next_status = board_command._step_heading_state(heading, direction=1)
    prev_state, prev_status = board_command._step_heading_state(heading, direction=-1)

    assert next_state == "DONE"
    assert next_status is None
    assert prev_state == "TODO"
    assert prev_status is None


def test_step_heading_state_boundary_no_ops() -> None:
    """Null-left and last-right should be no-op with status."""
    empty_heading = node_from_org("#+TODO: TODO | DONE\n* Task\n")[0]
    done_heading = node_from_org("#+TODO: TODO | DONE\n* DONE Task\n")[0]

    no_state, no_state_status = board_command._step_heading_state(empty_heading, direction=-1)
    last_state, last_state_status = board_command._step_heading_state(done_heading, direction=1)

    assert no_state is None
    assert no_state_status == "State unchanged"
    assert last_state == "DONE"
    assert last_state_status == "Already at last state"


def test_step_heading_state_deduplicates_document_states() -> None:
    """State stepping should deduplicate repeated all_states values."""
    heading = node_from_org("#+TODO: TODO TODO WAITING | DONE DONE\n* TODO Task\n")[0]

    new_state, status = board_command._step_heading_state(heading, direction=1)

    assert new_state == "WAITING"
    assert status is None


def test_apply_state_move_steps_state_and_reloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shift state move should persist, reload, and keep repeater behavior path."""
    args = make_board_args([])
    node = node_from_org("#+TODO: TODO | DONE\n* TODO Task\n")[0]
    session = board_command._BoardSession(
        args=args,
        nodes=[node],
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[board_command._BoardColumn("TODO", [node])],
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    saved_documents: list[Document] = []
    reloaded: list[tuple[str, str, str, int | None] | None] = []

    def _capture_save(document: Document) -> None:
        saved_documents.append(document)

    monkeypatch.setattr(board_command, "_save_document_changes", _capture_save)
    monkeypatch.setattr(
        board_command,
        "_reload_session",
        lambda _session, preserve_identity: reloaded.append(preserve_identity),
    )

    board_command._apply_state_move(session, direction=1)

    assert node.todo == "DONE"
    assert saved_documents == [node.document]
    assert len(reloaded) == 1
    assert session.status_message == "State updated: TODO -> DONE"


def test_reload_session_keeps_same_task_selected_after_priority_reshuffle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selection should stay on the same task after priority resorting."""
    args = make_board_args([])
    original_nodes = node_from_org("* TODO [#A] Other\n* TODO [#C] Focus\n")
    session = board_command._BoardSession(
        args=args,
        nodes=original_nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=board_command._build_selector_board_columns(
            original_nodes,
            board_command._resolve_column_specs(args),
        ),
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=1,
        scroll_offset=0,
        status_message="",
    )

    focused = session.columns[1].nodes[1]
    focused.priority = "A"
    preserve_identity = heading_identity(focused)

    reloaded_nodes = node_from_org("* TODO [#A] Other\n* TODO [#A] Focus\n")

    monkeypatch.setattr(
        board_command,
        "load_and_process_data",
        lambda _args: (reloaded_nodes, ["TODO"], ["DONE"]),
    )

    board_command._reload_session(session, preserve_identity)

    selected = board_command._selected_node(session)
    assert selected is not None
    assert selected.title_text == "Focus"


def test_interactive_renderable_keeps_footer_at_bottom() -> None:
    """Interactive render should reserve bottom lines for footer and status."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="Ready",
    )
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120, height=24)

    console.print(board_command._interactive_flow_board_renderable(console, session))
    lines = buffer.getvalue().splitlines()

    assert len(lines) == 24
    assert lines[-2].startswith("Rows ")
    assert "Type ? for help" in lines[-2]
    assert lines[-1].strip() == "Ready"


def test_interactive_renderable_footer_status_is_single_line() -> None:
    """Interactive footer status should be normalized to one visible line."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="line one\nline two\nline three",
    )
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120, height=24)

    console.print(board_command._interactive_flow_board_renderable(console, session))
    lines = buffer.getvalue().splitlines()

    assert len(lines) == 24
    assert lines[-2].startswith("Rows ")
    assert "Type ? for help" in lines[-2]
    assert lines[-1].strip() == "line one line two line three"


def test_handle_interactive_key_slash_activates_search_prompt() -> None:
    """Slash should activate board search prompt."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[board_command._BoardColumn("TODO", nodes)],
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        all_columns=[board_command._BoardColumn("TODO", nodes)],
    )

    assert board_command._handle_interactive_key(session, "/") is True
    assert session.active_interactive_action is not None
    assert (
        session.active_interactive_action.prompt_config.prompt.label == "Search text (blank clears)"
    )


def test_board_search_filters_each_column_and_clear_restores_columns() -> None:
    """Interactive search should filter each column's visible tasks and clear should restore."""
    args = make_board_args([])
    alpha, beta, beta_done = node_from_org(
        "* TODO Alpha\n* TODO Beta\n* DONE Beta done\n",
    )
    all_columns = [
        board_command._BoardColumn("Backlog", []),
        board_command._BoardColumn("TODO", [alpha, beta]),
        board_command._BoardColumn("DONE", [beta_done]),
    ]
    session = board_command._BoardSession(
        args=args,
        nodes=[alpha, beta, beta_done],
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=all_columns,
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        all_columns=all_columns,
    )

    assert board_command._handle_interactive_key(session, "/") is True
    assert session.active_interactive_action is not None
    session.active_interactive_action.prompt_config.prompt.value = "beta"
    submit_result = session.active_interactive_action.submit(session)

    assert submit_result.success is True
    assert submit_result.status_message == "2 matches"
    assert _visible_board_titles_by_column(session) == {
        "Backlog": [],
        "TODO": ["Beta"],
        "DONE": ["Beta done"],
    }
    assert session.search_text == "beta"

    assert board_command._handle_interactive_key(session, "x") is True
    assert session.status_message == "Search cleared"
    assert session.search_text == ""
    assert _visible_board_titles_by_column(session) == {
        "Backlog": [],
        "TODO": ["Alpha", "Beta"],
        "DONE": ["Beta done"],
    }


def test_interactive_renderable_footer_shows_active_search_text() -> None:
    """Board footer should include currently active interactive search text."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    column = board_command._BoardColumn("TODO", nodes)
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[column],
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        all_columns=[column],
        search_text="task",
    )
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120, height=24)

    console.print(board_command._interactive_flow_board_renderable(console, session))
    output = buffer.getvalue()

    assert "Search: task" in output


def test_handle_interactive_key_question_toggles_help_modal() -> None:
    """Question mark should open help modal and next key should close it."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[board_command._BoardColumn("TODO", nodes)],
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    assert board_command._handle_interactive_key(session, "?") is True
    assert session.show_help_modal is True

    assert board_command._handle_interactive_key(session, "ENTER") is True
    assert session.show_help_modal is False


def test_interactive_renderable_shows_help_panel() -> None:
    """Help modal should render key bindings panel in body area."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[board_command._BoardColumn("TODO", nodes)],
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        show_help_modal=True,
    )
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120, height=24)

    console.print(board_command._interactive_flow_board_renderable(console, session))
    output = buffer.getvalue()

    assert "Key bindings" in output
    assert "Type ? for help" not in output


def test_handle_interactive_key_enter_edits_selected_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter should trigger external-editor task editing for selected panel."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    def _fake_edit(_heading: Heading) -> editor_command.DocumentEditResult:
        return editor_command.DocumentEditResult(changed=False)

    monkeypatch.setattr(board_command, "edit_heading_subtree_in_external_editor", _fake_edit)

    assert board_command._handle_interactive_key(session, "ENTER") is True
    assert session.status_message == "No changes."


def test_state_shift_key_bindings_do_not_require_live_pause() -> None:
    """State shifts should run without stopping Live screen rendering."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[board_command._BoardColumn("TODO", nodes)],
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    bindings = board_command._flow_board_key_bindings(session)

    assert bindings["S-LEFT"].requires_live_pause is False
    assert bindings["S-RIGHT"].requires_live_pause is False
    assert bindings["ENTER"].requires_live_pause is True


def test_handle_interactive_key_a_captures_task_and_reloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a should prompt for template then capture and reload board selection."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Existing\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    captured_node = node_from_org("* TODO Captured\n")[0]
    reloaded: dict[str, object] = {}
    monkeypatch.setattr(
        config_module,
        "CONFIG_CAPTURE_TEMPLATES",
        {"quick": {"file": "tasks.org", "content": "* TODO Captured"}},
    )

    monkeypatch.setattr(
        board_command,
        "capture_task",
        lambda _args: capture_command.TasksCaptureResult(
            template_name="quick",
            heading=captured_node,
            document=captured_node.document,
        ),
    )

    def _fake_reload(
        current_session: board_command._BoardSession,
        preserve_identity: tuple[str, str, str, int | None] | None,
    ) -> None:
        reloaded["session"] = current_session
        reloaded["identity"] = preserve_identity

    monkeypatch.setattr(board_command, "_reload_session", _fake_reload)

    assert board_command._handle_interactive_key(session, "a") is True
    assert session.active_interactive_action is not None
    session.active_interactive_action.prompt_config.prompt.value = "1"
    submit_result = session.active_interactive_action.submit(session)
    assert submit_result.success is True
    assert submit_result.keep_prompt_open is False
    assert reloaded["session"] is session
    assert reloaded["identity"] == heading_identity(captured_node)
    assert session.status_message == "Task captured"


def test_handle_interactive_key_a_capture_blank_input_cancels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a should close prompt with cancel status on blank template input."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Existing\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    monkeypatch.setattr(
        config_module,
        "CONFIG_CAPTURE_TEMPLATES",
        {"quick": {"file": "tasks.org", "content": "* TODO Captured"}},
    )

    assert board_command._handle_interactive_key(session, "a") is True
    assert session.active_interactive_action is not None
    session.active_interactive_action.prompt_config.prompt.value = ""
    submit_result = session.active_interactive_action.submit(session)
    assert submit_result.success is True
    assert submit_result.keep_prompt_open is False
    assert submit_result.status_message == "Capture cancelled"


def test_handle_interactive_key_a_capture_invalid_shortcut_keeps_prompt_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a should keep capture prompt open for invalid template shortcuts."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Existing\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    monkeypatch.setattr(
        config_module,
        "CONFIG_CAPTURE_TEMPLATES",
        {"quick": {"file": "tasks.org", "content": "* TODO Captured"}},
    )

    assert board_command._handle_interactive_key(session, "a") is True
    assert session.active_interactive_action is not None
    session.active_interactive_action.prompt_config.prompt.value = "99"
    submit_result = session.active_interactive_action.submit(session)

    assert submit_result.success is False
    assert submit_result.keep_prompt_open is True
    assert submit_result.status_message == "Invalid capture template shortcut"


def test_handle_interactive_key_a_without_templates_reports_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a should report a clear status when no capture templates are configured."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Existing\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    monkeypatch.setattr(config_module, "CONFIG_CAPTURE_TEMPLATES", {})

    assert board_command._handle_interactive_key(session, "a") is True
    assert session.active_interactive_action is None
    assert session.status_message == "No capture templates configured"


def test_handle_active_prompt_input_capture_submit_stops_and_restarts_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board prompt submission should pause live rendering for capture action."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Existing\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    monkeypatch.setattr(
        config_module,
        "CONFIG_CAPTURE_TEMPLATES",
        {"quick": {"file": "tasks.org", "content": "* TODO Captured"}},
    )
    board_command._handle_interactive_key(session, "a")
    assert session.active_interactive_action is not None
    session.active_interactive_action.prompt_config.prompt.value = "1"

    captured_node = node_from_org("* TODO Captured\n")[0]
    monkeypatch.setattr(
        board_command,
        "capture_task",
        lambda _args: capture_command.TasksCaptureResult(
            template_name="quick",
            heading=captured_node,
            document=captured_node.document,
        ),
    )
    monkeypatch.setattr(board_command, "_reload_session", lambda _session, _identity: None)
    monkeypatch.setattr(
        interactive_actions,
        "read_input_event_with_timeout",
        lambda _timeout, **_kwargs: ("ENTER", ""),
    )

    events: list[str] = []

    class _LiveStub:
        console = Console(file=StringIO(), force_terminal=False, width=120, height=24)

        def stop(self) -> None:
            events.append("stop")

        def start(self) -> None:
            events.append("start")

        def update(self, _renderable: object, refresh: bool) -> None:
            assert refresh is True
            events.append("update")

    consumed = board_command._handle_active_prompt_input(session, cast("Live", _LiveStub()))

    assert consumed is True
    assert events == ["stop", "start", "update"]


def test_search_prompt_live_updates_and_escape_reverts_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board search prompt should live-update columns and ESC should restore prior filter."""
    args = make_board_args([])
    alpha, beta, done = node_from_org("* TODO Alpha\n* TODO Beta\n* DONE Finished\n")
    all_columns = [
        board_command._BoardColumn("Backlog", []),
        board_command._BoardColumn("TODO", [alpha, beta]),
        board_command._BoardColumn("DONE", [done]),
    ]
    session = board_command._BoardSession(
        args=args,
        nodes=[alpha, beta, done],
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=all_columns,
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        all_columns=all_columns,
    )
    assert board_command._handle_interactive_key(session, "/") is True
    assert session.active_interactive_action is not None

    events: list[str] = []

    class _LiveStub:
        console = Console(file=StringIO(), force_terminal=False, width=120, height=24)

        def stop(self) -> None:
            events.append("stop")

        def start(self) -> None:
            events.append("start")

        def update(self, _renderable: object, refresh: bool) -> None:
            assert refresh is True
            events.append("update")

    monkeypatch.setattr(
        interactive_actions,
        "read_input_event_with_timeout",
        lambda _timeout, **_kwargs: ("TEXT", "b"),
    )
    consumed = board_command._handle_active_prompt_input(session, cast("Live", _LiveStub()))

    assert consumed is True
    assert _visible_board_titles_by_column(session) == {
        "Backlog": [],
        "TODO": ["Beta"],
        "DONE": [],
    }
    assert session.search_text == "b"
    assert session.status_message == "1 matches"

    monkeypatch.setattr(
        interactive_actions,
        "read_input_event_with_timeout",
        lambda _timeout, **_kwargs: ("ESC", ""),
    )
    consumed = board_command._handle_active_prompt_input(session, cast("Live", _LiveStub()))

    assert consumed is True
    assert _visible_board_titles_by_column(session) == {
        "Backlog": [],
        "TODO": ["Alpha", "Beta"],
        "DONE": ["Finished"],
    }
    assert session.search_text == ""
    assert session.status_message == "Search cancelled"
    assert events == ["update", "update"]


def test_handle_interactive_key_enter_saves_original_document_after_changed_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changed edit should save the selected task's original document."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    source_node = nodes[0]

    def _fake_edit(_heading: Heading) -> editor_command.DocumentEditResult:
        return editor_command.DocumentEditResult(changed=True)

    reloaded_identity = None

    def _capture_reload(_session: board_command._BoardSession, identity: object) -> None:
        nonlocal reloaded_identity
        reloaded_identity = identity

    monkeypatch.setattr(board_command, "edit_heading_subtree_in_external_editor", _fake_edit)
    monkeypatch.setattr(board_command, "_reload_session", _capture_reload)

    assert board_command._handle_interactive_key(session, "ENTER") is True
    assert session.status_message == "Task updated"
    assert reloaded_identity == heading_identity(source_node)


def test_handle_interactive_key_dollar_archives_selected_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """$ should archive highlighted task using shared archive helper."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = board_command._BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=[
            board_command._BoardColumn("NOT STARTED", []),
            board_command._BoardColumn("TODO", nodes),
            board_command._BoardColumn("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    def _fake_archive(
        heading: Heading,
        _cache: dict[str, Document],
    ) -> archive_command.ArchiveMoveResult:
        location = archive_command.ArchiveLocation(
            raw_spec="%s_archive::",
            file_path="tasks.org_archive",
            parent_title=None,
        )
        target = archive_command.ArchiveTarget(
            location=location,
            document=heading.document,
            parent_heading=None,
        )
        return archive_command.ArchiveMoveResult(
            heading=heading,
            target=target,
            source_document=heading.document,
            destination_document=heading.document,
        )

    monkeypatch.setattr(board_command, "archive_heading_subtree_and_save", _fake_archive)
    monkeypatch.setattr(board_command, "_reload_session", lambda _session, _identity: None)

    assert board_command._handle_interactive_key(session, "$") is True
    assert session.status_message == "Task archived"


def test_run_flow_board_does_not_hide_unknown_or_empty_states(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown and empty task states should still be visible on the board."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], width=120)

    monkeypatch.setattr(sys, "argv", ["org", "board"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Task without any state" in output
    assert "WAITING Custom todo state" in output


def test_run_flow_board_no_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should print No results when filters remove all tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "board", "--filter-tag", "nomatch$"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert output.strip() == "No results"


def test_run_flow_board_rejects_width_below_80(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should reject console widths below the minimum."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], width=79)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "79"])
    with pytest.raises(typer.BadParameter, match="--width must be at least 80"):
        board_command.run_flow_board(args)


def test_run_flow_board_limit_applies_before_grouping(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should respect --limit when selecting processed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=1)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--limit", "1"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Refactor codebase" in output
    assert "Fix bug in parser" not in output


def test_run_flow_board_offset_applies_before_grouping(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should respect --offset when selecting processed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=1, offset=1, days=100000)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--offset", "1", "--limit", "1"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Refactor codebase" not in output
    assert "Fix bug in parser" in output


def test_run_flow_board_negative_max_results_raises_bad_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should reject negative --limit values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=-1)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--limit", "-1"])
    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        board_command.run_flow_board(args)


def test_run_flow_board_negative_offset_raises_bad_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should reject negative --offset values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], offset=-1)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--offset", "-1"])
    with pytest.raises(typer.BadParameter, match="--offset must be non-negative"):
        board_command.run_flow_board(args)


def test_run_flow_board_uses_pager_when_render_exceeds_console_height(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Board output should use pager when rendered board exceeds viewport height."""
    fixture_path = os.path.join(tmp_path, "many_tasks_board.org")
    tasks = "\n".join(f"* TODO Task {index}" for index in range(15))
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(tasks)

    console = Console(
        width=90,
        height=6,
        file=StringIO(),
        no_color=True,
        force_terminal=False,
    )
    pager_called = {"value": False}

    @contextmanager
    def _fake_pager(*args: object, **kwargs: object) -> Iterator[None]:
        del args, kwargs
        pager_called["value"] = True
        yield

    monkeypatch.setattr(console, "pager", _fake_pager)
    monkeypatch.setattr("org.commands.board.build_console", lambda _color, _width: console)

    args = make_board_args([fixture_path], max_results=None)
    monkeypatch.setattr(sys, "argv", ["org", "board"])
    board_command.run_flow_board(args)

    assert pager_called["value"]


def test_run_flow_board_selector_uses_full_nodes_from_multiple_files(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Selector passes should evaluate across all loaded files as one processed list."""
    first_path = os.path.join(tmp_path, "first.org")
    second_path = os.path.join(tmp_path, "second.org")
    with open(first_path, "w", encoding="utf-8") as first_handle:
        first_handle.write("* TODO First file task\n")
    with open(second_path, "w", encoding="utf-8") as second_handle:
        second_handle.write("* TODO Second file task\n")

    args = make_board_args([first_path, second_path], view="kanban", width=160)
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(name="TODO", filter='str(.todo) == "TODO"'),
        ],
    )

    try:
        monkeypatch.setattr(sys, "argv", ["org", "board", "--view", "kanban", "--width", "160"])
        board_command.run_flow_board(args)
        output = capsys.readouterr().out
        assert "First file task" in output
        assert "Second file task" in output
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_coalesce_completed_true_shows_completed_column(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback selector view should include DONE column for completed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    _pin_board_now(monkeypatch)
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "DONE" in output
    assert "Completed task" in output


def test_run_flow_board_coalesce_completed_true_prefixes_state_in_panel(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback DONE selector should include all completed state tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    _pin_board_now(monkeypatch)
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Completed task" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_run_flow_board_coalesce_completed_false_shows_individual_done_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback selector view should not render legacy COMPLETED header."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    _pin_board_now(monkeypatch)
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "COMPLETED" not in output
    assert "DONE" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_run_flow_board_coalesce_completed_false_done_columns_ordered_after_todo_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback selector headers should stay in Backlog/TODO/DONE order."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    _pin_board_now(monkeypatch)
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    pos_in_progress = output.find("TODO")
    pos_done = output.find("DONE")

    assert pos_in_progress != -1
    assert pos_done != -1
    assert pos_in_progress < pos_done


def test_run_flow_board_coalesce_completed_false_tasks_in_correct_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback DONE selector should show all completed-state tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    _pin_board_now(monkeypatch)
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Completed task" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_run_flow_board_uses_configured_view_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requested configured view should render configured columns."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], view="kanban", width=150)
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(
                name="Backlog",
                filter=".todo == null",
            ),
            config_module.BoardColumnConfig(
                name="Working",
                filter=".todo != null and not(.is_completed)",
            ),
        ],
    )

    try:
        monkeypatch.setattr(sys, "argv", ["org", "board", "--view", "kanban", "--width", "150"])
        board_command.run_flow_board(args)
        output = capsys.readouterr().out
        assert "Backlog" in output
        assert "Working" in output
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_missing_requested_view_raises() -> None:
    """Missing requested view should return explicit BadParameter."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="missing")
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["other"] = config_module.BoardViewConfig(
        name="other",
        columns=[
            config_module.BoardColumnConfig(
                name="TODO",
                filter='.todo == "TODO"',
            ),
        ],
    )
    try:
        with pytest.raises(typer.BadParameter, match="Requested board view not found"):
            board_command.run_flow_board(args)
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_requested_view_without_configured_views_raises() -> None:
    """Explicit --view should fail when no configured views exist."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    try:
        with pytest.raises(typer.BadParameter, match="no board views are configured"):
            board_command.run_flow_board(args)
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_uses_default_view_from_config(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config-defaulted view value should drive board view resolution."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], view=None, width=150)
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(name="Backlog", filter=".todo == null"),
            config_module.BoardColumnConfig(
                name="Working",
                filter=".todo != null and not(.is_completed)",
            ),
        ],
    )

    try:
        # Simulate Typer default_map applying defaults: --view=kanban
        args.view = "kanban"
        specs = board_command._resolve_column_specs(args)
        assert [spec.name for spec in specs] == ["Backlog", "Working"]
        monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "150"])
        board_command.run_flow_board(args)
        output = capsys.readouterr().out
        assert "Backlog" in output
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_invalid_filter_or_order_by_parse_error_has_context() -> None:
    """Filter/order-by parse failures should include view and column context."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(name="Broken", filter=".todo =="),
        ],
    )
    try:
        with pytest.raises(typer.BadParameter, match="view=kanban, column=Broken"):
            board_command.run_flow_board(args)
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_invalid_filter_or_order_by_runtime_error_has_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter/order-by runtime failures should include view and column context."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(
                name="Broken",
                filter="unknown_fn(.todo)",
            ),
        ],
    )
    monkeypatch.setattr(
        board_command,
        "load_and_process_data",
        lambda _args: ([node_from_org("* TODO Task\n")[0]], ["TODO"], ["DONE"]),
    )
    try:
        with pytest.raises(typer.BadParameter, match="view=kanban, column=Broken"):
            board_command.run_flow_board(args)
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_run_flow_board_invalid_order_by_parse_error_has_context() -> None:
    """Invalid order-by parse should include view and column context."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(
                name="Broken",
                filter='.todo == "TODO"',
                order_by=".priority ==",
            ),
        ],
    )
    try:
        with pytest.raises(
            typer.BadParameter,
            match=r"Invalid board filter/order-by \(view=kanban, column=Broken\)",
        ):
            board_command.run_flow_board(args)
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_apply_state_move_reload_reassigns_task_across_selector_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State changes should reload and move task to new selector column."""
    args = make_board_args([], view="kanban", days=100000)
    source_node = node_from_org("#+TODO: TODO | DONE\n* TODO Task\n")[0]
    original_views = dict(config_module.CONFIG_BOARD_VIEWS)
    config_module.CONFIG_BOARD_VIEWS.clear()
    config_module.CONFIG_BOARD_VIEWS["kanban"] = config_module.BoardViewConfig(
        name="kanban",
        columns=[
            config_module.BoardColumnConfig(name="TODO", filter='.todo == "TODO"'),
            config_module.BoardColumnConfig(name="DONE", filter='.todo == "DONE"'),
        ],
    )

    session = board_command._BoardSession(
        args=args,
        nodes=[source_node],
        todo_states=["TODO"],
        done_states=["DONE"],
        columns=board_command._build_selector_board_columns(
            [source_node],
            board_command._resolve_column_specs(args),
        ),
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    saved_documents: list[Document] = []

    def _capture_save(document: Document) -> None:
        saved_documents.append(document)

    def _load_after_change(
        _args: board_command.BoardArgs,
    ) -> tuple[list[Heading], list[str], list[str]]:
        if source_node.todo == "DONE":
            return (
                node_from_org(
                    "#+TODO: TODO | DONE\n* DONE Task\nCLOSED: [2026-05-08 Fri 09:00]\n",
                ),
                ["TODO"],
                ["DONE"],
            )
        return ([source_node], ["TODO"], ["DONE"])

    monkeypatch.setattr(board_command, "_save_document_changes", _capture_save)
    monkeypatch.setattr(board_command, "load_and_process_data", _load_after_change)

    try:
        board_command._apply_state_move(session, direction=1)
        assert saved_documents == [source_node.document]
        assert session.selected_column_index == 1
        selected = board_command._selected_node(session)
        assert selected is not None
        assert selected.todo == "DONE"
    finally:
        config_module.CONFIG_BOARD_VIEWS.clear()
        config_module.CONFIG_BOARD_VIEWS.update(original_views)


def test_build_task_panel_renders_rich_title_content() -> None:
    """Flow board panels should render heading RichText with Rich styles."""
    nodes = node_from_org(
        (
            "* TODO *Bold* /Italic/ _Underline_ +Strike+ =Verbatim= ~InlineCode~ "
            "[[https://example.com/docs][Docs]] x^{2} H_{2}O src_python{1+1} "
            "call_fn(1)\n"
        ),
    )

    panel = board_command._build_task_panel(
        nodes[0],
        board_command._BoardPanelRenderConfig(
            width=60,
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
        highlighted=False,
    )

    assert isinstance(panel.renderable, Text)
    markup = panel.renderable.markup
    plain = panel.renderable.plain

    assert "[bold]Bold[/bold]" in markup
    assert "[italic]Italic[/italic]" in markup
    assert "[underline]Underline[/underline]" in markup
    assert "[strike]Strike[/strike]" in markup
    assert "[link https://example.com/docs]Docs[/link https://example.com/docs]" in markup

    assert "*Bold*" not in plain
    assert "/Italic/" not in plain
    assert "_Underline_" not in plain
    assert "+Strike+" not in plain
    assert "=Verbatim=" not in plain
    assert "~InlineCode~" not in plain
    assert "x^{2}" in plain
    assert "H_{2}O" in plain
    assert "src_python{1+1}" in plain
    assert "call_fn(1)" in plain


def test_run_flow_board_renders_rich_title_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Flow board command should print rich title text without org inline delimiters."""
    fixture_path = os.path.join(tmp_path, "rich_board.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO *Bold* /Italic/ _Underline_ +Strike+ =Verbatim= ~InlineCode~ "
            "[[https://example.com/docs][Docs]] x^{2} H_{2}O src_python{1+1} call_fn(1)\n",
        )

    args = make_board_args([fixture_path], width=120)
    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "120"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Bold" in output
    assert "Italic" in output
    assert "Underline" in output
    assert "Strike" in output
    assert "Verbatim" in output
    assert "InlineCode" in output
    assert "Docs" in output
    assert "x^{2}" in output
    assert "H_{2}O" in output
    assert "src_python{1+1}" in output
    assert "call_fn(1)" in output

    assert "*Bold*" not in output
    assert "/Italic/" not in output
    assert "_Underline_" not in output
    assert "+Strike+" not in output
    assert "=Verbatim=" not in output
    assert "~InlineCode~" not in output
    assert "[[https://example.com/docs][Docs]]" not in output


def test_build_task_panel_shows_colored_todo_state_prefix() -> None:
    """Task panels should show and colorize current TODO state."""
    node = node_from_org("#+TODO: TODO WAITING | DONE\n* TODO Task\n")[0]

    panel = board_command._build_task_panel(
        node,
        board_command._BoardPanelRenderConfig(
            width=60,
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO", "WAITING"],
        ),
        highlighted=False,
    )

    renderable = panel.renderable
    assert isinstance(renderable, Text)
    assert renderable.plain.startswith("TODO Task")
    assert renderable.spans


def test_build_task_panel_without_todo_state_has_no_prefix() -> None:
    """Task panels without TODO state should keep heading text unchanged."""
    node = node_from_org("* Task without state\n")[0]

    panel = board_command._build_task_panel(
        node,
        board_command._BoardPanelRenderConfig(
            width=60,
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
        ),
        highlighted=False,
    )

    renderable = panel.renderable
    assert isinstance(renderable, Text)
    assert renderable.plain.startswith("Task without state")
