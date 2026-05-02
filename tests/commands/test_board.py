"""Tests for board command."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from io import StringIO
from typing import TYPE_CHECKING

import pytest
import typer
from rich.console import Console
from rich.text import Text

from org.commands import archive as archive_command
from org.commands import board as board_command
from org.commands import editor as editor_command
from org.commands.interactive_common import heading_identity
from org.commands.tasks import capture as capture_command
from tests.conftest import node_from_org


if TYPE_CHECKING:
    from collections.abc import Iterator

    from org_parser.document import Document, Heading


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
        width=120,
        max_results=None,
        offset=0,
        order_by_level=False,
        order_by_file_order=False,
        order_by_file_order_reversed=False,
        order_by_priority=False,
        order_by_timestamp_asc=False,
        order_by_timestamp_desc=False,
        with_tags_as_category=False,
        coalesce_completed=True,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_flow_board_renders_expected_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should render NOT STARTED, todo columns, and COMPLETED."""
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

    assert "NOT STARTED" in output
    assert "TODO" in output
    assert "WAITING" in output
    assert "IN-PROGRESS" in output
    assert "COMPLETED" in output


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
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--order-by-file-order"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    first = output.find("Refactor codebase")
    second = output.find("Fix bug in parser")
    assert first != -1
    assert second != -1
    assert first < second


def test_build_flow_board_columns_orders_by_priority() -> None:
    """Lane content should be ordered from highest to lowest priority."""
    nodes = node_from_org(
        "* TODO [#C] Low\n* TODO Middle\n* TODO [#A] High\n* TODO [#B] Medium\n",
    )

    columns = board_command._build_flow_board_columns(
        nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        coalesce_completed=True,
    )

    todo_column = next(column for column in columns if column.title == "TODO")
    assert [node.title_text for node in todo_column.nodes] == ["High", "Medium", "Low", "Middle"]


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
        coalesce_completed=True,
    )
    row_heights = board_command._interactive_row_heights(session, render)
    _start, _end, _used = board_command._sync_scroll_for_selection(
        session,
        row_heights,
        available_lines=8,
    )

    assert session.scroll_offset == 3


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
        columns=board_command._build_flow_board_columns(
            original_nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            coalesce_completed=True,
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
    assert "Enter edit" in lines[-2]
    assert "$ archive" in lines[-2]
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
    assert lines[-1].strip() == "line one line two line three"


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
    console = Console(file=StringIO(), force_terminal=False)

    def _fake_edit(heading: Heading) -> editor_command.HeadingEditResult:
        return editor_command.HeadingEditResult(heading=heading, changed=False)

    monkeypatch.setattr(board_command, "edit_heading_subtree_in_external_editor", _fake_edit)

    assert board_command._handle_interactive_key(console, session, "ENTER") is True
    assert session.status_message == "No changes."


def test_handle_interactive_key_a_captures_task_and_reloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a should capture a task and reload board selection."""
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
    console = Console(file=StringIO(), force_terminal=False)
    captured_node = node_from_org("* TODO Captured\n")[0]
    reloaded: dict[str, object] = {}

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

    assert board_command._handle_interactive_key(console, session, "a") is True
    assert reloaded["session"] is session
    assert reloaded["identity"] == heading_identity(captured_node)
    assert session.status_message == "Task captured"


def test_handle_interactive_key_a_capture_cancelled_sets_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a should report cancellation when capture is interrupted."""
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
    console = Console(file=StringIO(), force_terminal=False)

    def _raise_interrupt(
        _args: capture_command.TasksCaptureArgs,
    ) -> capture_command.TasksCaptureResult:
        raise KeyboardInterrupt

    monkeypatch.setattr(board_command, "capture_task", _raise_interrupt)

    assert board_command._handle_interactive_key(console, session, "a") is True
    assert session.status_message == "Capture cancelled"


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
    console = Console(file=StringIO(), force_terminal=False)
    source_document = nodes[0].document
    detached_heading = node_from_org("* TODO Updated\n")[0]

    def _fake_edit(_heading: Heading) -> editor_command.HeadingEditResult:
        return editor_command.HeadingEditResult(heading=detached_heading, changed=True)

    saved_documents: list[Document] = []

    def _capture_save(document: Document) -> None:
        saved_documents.append(document)

    monkeypatch.setattr(board_command, "edit_heading_subtree_in_external_editor", _fake_edit)
    monkeypatch.setattr(board_command, "_save_document_changes", _capture_save)
    monkeypatch.setattr(board_command, "_reload_session", lambda _session, _identity: None)

    assert board_command._handle_interactive_key(console, session, "ENTER") is True
    assert session.status_message == "Task updated"
    assert saved_documents == [source_document]


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
    console = Console(file=StringIO(), force_terminal=False)

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

    assert board_command._handle_interactive_key(console, session, "$") is True
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
    args = make_board_args([fixture_path], max_results=1, offset=1)

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


def test_run_flow_board_coalesce_completed_true_shows_completed_column(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With coalesce_completed=True, all done tasks appear under a single COMPLETED column."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        coalesce_completed=True,
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "COMPLETED" in output
    assert "DONE" not in output.split("COMPLETED")[0].replace("NOT STARTED", "")
    assert "CANCELLED" not in output.split("COMPLETED")[0].replace("NOT STARTED", "")
    assert "ARCHIVED" not in output.split("COMPLETED")[0].replace("NOT STARTED", "")


def test_run_flow_board_coalesce_completed_true_prefixes_state_in_panel(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With coalesce_completed=True, each completed task panel shows its state in the title."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        coalesce_completed=True,
        width=200,
    )

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "200"])
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "DONE Completed task" in output
    assert "CANCELLED Custom done state" in output
    assert "ARCHIVED Another done state" in output


def test_run_flow_board_coalesce_completed_false_shows_individual_done_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With coalesce_completed=False, each done state gets its own column header."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        coalesce_completed=False,
        width=200,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "board", "--no-coalesce-completed", "--width", "200"],
    )
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "COMPLETED" not in output
    assert "DONE" in output
    assert "CANCELLED" in output
    assert "ARCHIVED" in output


def test_run_flow_board_coalesce_completed_false_done_columns_ordered_after_todo_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With coalesce_completed=False, done key columns appear to the right of todo key columns."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        coalesce_completed=False,
        width=200,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "board", "--no-coalesce-completed", "--width", "200"],
    )
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    pos_in_progress = output.find("IN-PROGRESS")
    pos_done = output.find("DONE")
    pos_cancelled = output.find("CANCELLED")
    pos_archived = output.find("ARCHIVED")

    assert pos_in_progress != -1
    assert pos_done != -1
    assert pos_cancelled != -1
    assert pos_archived != -1
    assert pos_in_progress < pos_done
    assert pos_done < pos_cancelled
    assert pos_cancelled < pos_archived


def test_run_flow_board_coalesce_completed_false_tasks_in_correct_columns(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With coalesce_completed=False, tasks appear under their specific done state column."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_states="TODO,WAITING,IN-PROGRESS",
        done_states="DONE,CANCELLED,ARCHIVED",
        coalesce_completed=False,
        width=200,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "board", "--no-coalesce-completed", "--width", "200"],
    )
    board_command.run_flow_board(args)
    output = capsys.readouterr().out

    assert "Completed task" in output
    assert "Custom done state" in output
    assert "Another done state" in output


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
            coalesce_completed=True,
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
