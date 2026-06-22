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

import org.config.app
from org.commands.board import actions, ui
from org.commands.board import command as board_command
from org.logic.archive import ArchiveLocation, ArchiveMoveResult, ArchiveTarget
from org.logic.edit import DocumentEditResult
from org.logic.tasks import heading_locator
from org.pipeline.load import load_and_process_data
from org.tui.bits import setup_output
from tests.conftest import node_from_org


if TYPE_CHECKING:
    from collections.abc import Iterator

    from org_parser.document import Document, Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _board_views_configured() -> dict[str, org.config.app.BoardViewConfig]:
    """Build a reusable configured board view set for tests."""
    return {
        "kanban": org.config.app.BoardViewConfig(
            name="kanban",
            columns=[
                org.config.app.BoardColumnConfig(name="Backlog", filter=".todo == null"),
                org.config.app.BoardColumnConfig(
                    name="Working",
                    filter=".todo != null and not(.is_completed)",
                ),
            ],
        ),
    }


def _app_config(
    *,
    board_views: dict[str, org.config.app.BoardViewConfig] | None = None,
) -> org.config.app.AppConfig:
    """Build app config for board tests with optional configured views."""
    config = org.config.app.AppConfig(config_path=".org-cli.yaml")
    if board_views is not None:
        config.board.views = board_views
    return config


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
    session: actions.BoardSession,
) -> dict[str, list[str]]:
    """Return visible task titles grouped by board column title."""
    return {column.title: [node.title_text for node in column.nodes] for column in session.columns}


def _col(title: str, nodes: list[Heading]) -> actions.BoardColumn:
    return actions.BoardColumn(title, nodes)


def _default_columns(nodes: list[Heading]) -> list[actions.BoardColumn]:
    return [_col("TODO", nodes)]


def _make_session(
    args: board_command.BoardArgs,
    nodes: list[Heading],
    **overrides: object,
) -> actions.BoardSession:
    app_config = cast(
        "org.config.app.AppConfig",
        overrides.pop("app_config", _app_config()),
    )
    resolved_columns = cast(
        "list[actions.BoardColumn] | None",
        overrides.pop("columns", None),
    )
    resolved_all_columns = cast(
        "list[actions.BoardColumn] | None",
        overrides.pop("all_columns", None),
    )
    session = actions.BoardSession(
        args=args,
        nodes=nodes,
        todo_states=["TODO"],
        done_states=["DONE"],
        app_config=app_config,
        columns=_default_columns(nodes) if resolved_columns is None else resolved_columns,
        color_enabled=False,
        selected_column_index=0,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        all_columns=[],
        search_text="",
    )
    session.all_columns = session.columns if resolved_all_columns is None else resolved_all_columns
    for key, value in overrides.items():
        setattr(session, key, value)
    return session


def _pin_board_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin board command current time for deterministic completed-task windows."""
    monkeypatch.setattr(
        actions,
        "local_now",
        lambda: datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
    )


def _render_board_output(args: board_command.BoardArgs) -> str:
    """Render board output through shared UI helpers for rendering tests."""
    return _render_board_output_with_config(args, _app_config())


def _render_board_output_with_config(
    args: board_command.BoardArgs,
    config: org.config.app.AppConfig,
) -> str:
    """Render board output through shared UI helpers for rendering tests."""
    color_enabled = setup_output(args)
    args.max_results = board_command._resolve_tasks_limit(args.max_results)
    console_output = StringIO()
    console = Console(
        file=console_output,
        width=args.width or 120,
        no_color=not color_enabled,
        force_terminal=color_enabled,
    )
    nodes, discovered_todo_states, discovered_done_states = load_and_process_data(
        args,
        config,
    )
    nodes = actions.filter_recent_completed_nodes(nodes, args.days)
    todo_states, done_states = actions.resolved_states(
        args,
        discovered_todo_states,
        discovered_done_states,
    )
    if not nodes:
        return "No results\n"
    columns = actions.build_selector_board_columns(
        nodes,
        actions.resolve_column_specs(args, config.board.views),
    )
    ui.render_static_board(
        console,
        columns,
        done_states=done_states,
        todo_states=todo_states,
        color_enabled=color_enabled,
    )
    return console_output.getvalue()


def test_filter_recent_completed_nodes_uses_latest_timestamp_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed tasks should be filtered by latest_timestamp recency."""
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(actions, "local_now", lambda: now)

    nodes = node_from_org(
        "* TODO Active task\n"
        "* DONE Recent done\n"
        "CLOSED: [2026-05-08 Fri 09:00]\n"
        "* DONE Old done\n"
        "CLOSED: [2026-04-01 Wed 09:00]\n",
    )

    filtered = actions.filter_recent_completed_nodes(nodes, days=7)

    assert [node.title_text for node in filtered] == ["Active task", "Recent done"]


def test_filter_recent_completed_nodes_respects_days_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Days override should widen completed-task retention window."""
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(actions, "local_now", lambda: now)

    nodes = node_from_org(
        "* DONE Mid-age done\nCLOSED: [2026-04-25 Sat 09:00]\n",
    )

    assert actions.filter_recent_completed_nodes(nodes, days=7) == []
    assert [node.title_text for node in actions.filter_recent_completed_nodes(nodes, days=30)] == [
        "Mid-age done",
    ]


def test_run_board_renders_expected_columns(monkeypatch: pytest.MonkeyPatch) -> None:
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
    output = _render_board_output(args)

    assert "Backlog" in output
    assert "TODO" in output
    assert "DONE" in output


def test_run_board_column_order_follows_document_todo_order(
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
    output = _render_board_output(args)

    pos_not_started = output.find("Backlog")
    pos_todo = output.find("TODO")
    pos_done = output.find("DONE")

    assert pos_not_started != -1
    assert pos_todo != -1
    assert pos_done != -1
    assert pos_not_started < pos_todo
    assert pos_todo < pos_done


def test_run_board_preserves_order_in_column_when_priorities_equal(
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
    output = _render_board_output(args)

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

    specs = actions.resolve_column_specs(make_board_args([]), {})
    columns = actions.build_selector_board_columns(nodes, specs)

    todo_column = next(column for column in columns if column.title == "TODO")
    assert [node.title_text for node in todo_column.nodes] == ["Low", "Middle", "High", "Medium"]


def test_build_selector_board_columns_with_order_by_overrides_processed_order() -> None:
    """Column order-by should apply sort_by selector after filtering."""
    nodes = node_from_org(
        "* TODO a\n* TODO c\n* TODO b\n",
    )
    view = org.config.app.BoardViewConfig(
        name="ordered",
        columns=[
            org.config.app.BoardColumnConfig(
                name="TODO",
                filter=".todo != null",
                order_by=".title_text",
            ),
        ],
    )

    columns = actions.build_selector_board_columns(
        nodes,
        actions.compile_view_column_specs(view),
    )

    todo_column = next(column for column in columns if column.title == "TODO")
    assert [node.title_text for node in todo_column.nodes] == ["c", "b", "a"]


def test_build_selector_board_columns_allows_matches_in_multiple_columns() -> None:
    """One task can appear in multiple selector columns."""
    nodes = node_from_org("* TODO Shared\n* DONE Finished\n")
    view = org.config.app.BoardViewConfig(
        name="overlap",
        columns=[
            org.config.app.BoardColumnConfig(name="Any todo", filter=".todo != null"),
            org.config.app.BoardColumnConfig(name="Open", filter="not(.is_completed)"),
        ],
    )

    columns = actions.build_selector_board_columns(
        nodes,
        actions.compile_view_column_specs(view),
    )

    any_todo_column = next(column for column in columns if column.title == "Any todo")
    open_column = next(column for column in columns if column.title == "Open")
    assert [node.title_text for node in any_todo_column.nodes] == ["Shared", "Finished"]
    assert [node.title_text for node in open_column.nodes] == ["Shared"]


def test_build_selector_board_columns_omits_non_matching_tasks() -> None:
    """Tasks that match no selectors should not appear in any column."""
    nodes = node_from_org("* TODO Open\n* DONE Closed\n")
    view = org.config.app.BoardViewConfig(
        name="nomatch",
        columns=[
            org.config.app.BoardColumnConfig(name="Backlog", filter=".todo == null"),
        ],
    )

    columns = actions.build_selector_board_columns(
        nodes,
        actions.compile_view_column_specs(view),
    )

    assert len(columns) == 1
    assert columns[0].title == "Backlog"
    assert columns[0].nodes == []


def test_render_column_title_text_allows_rich_markup() -> None:
    """Column titles should support Rich markup syntax."""
    title = ui.render_column_title_text("[bold green]Complete[/]")

    assert title.plain == "Complete"
    assert title.spans


def test_render_column_title_text_falls_back_on_invalid_markup() -> None:
    """Invalid markup in column title should render as literal text."""
    title = ui.render_column_title_text("[bold")

    assert title.plain == "[bold"


def test_move_selection_horizontal_skips_empty_columns() -> None:
    """Horizontal navigation should skip empty lanes."""
    args = make_board_args([])
    first, second = node_from_org("* TODO First\n* TODO Second\n")
    session = _make_session(
        args=args,
        nodes=[first, second],
        columns=[
            _col("NOT STARTED", []),
            _col("TODO", [first]),
            _col("WAITING", []),
            _col("INPROGRESS", [second]),
            _col("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    assert session.selected_column_index == 1
    actions.move_selection_horizontal(session, 1)
    assert session.selected_column_index == 3

    actions.move_selection_horizontal(session, -1)
    assert session.selected_column_index == 1


def test_step_heading_state_right_from_none_uses_first_document_state() -> None:
    """Shift-right from empty state should use first all_states item."""
    heading = node_from_org("#+TODO: TODO WAITING | DONE\n* Task\n")[0]

    new_state, status = actions.step_heading_state(heading, direction=1)

    assert new_state == "TODO"
    assert status is None


def test_step_heading_state_left_from_first_moves_to_none() -> None:
    """Shift-left from first state should clear todo state."""
    heading = node_from_org("#+TODO: TODO WAITING | DONE\n* TODO Task\n")[0]

    new_state, status = actions.step_heading_state(heading, direction=-1)

    assert new_state is None
    assert status is None


def test_step_heading_state_moves_prev_next_in_middle() -> None:
    """Shift-left/right should move through middle states."""
    heading = node_from_org("#+TODO: TODO WAITING | DONE\n* WAITING Task\n")[0]

    next_state, next_status = actions.step_heading_state(heading, direction=1)
    prev_state, prev_status = actions.step_heading_state(heading, direction=-1)

    assert next_state == "DONE"
    assert next_status is None
    assert prev_state == "TODO"
    assert prev_status is None


def test_step_heading_state_boundary_no_ops() -> None:
    """Null-left and last-right should be no-op with status."""
    empty_heading = node_from_org("#+TODO: TODO | DONE\n* Task\n")[0]
    done_heading = node_from_org("#+TODO: TODO | DONE\n* DONE Task\n")[0]

    no_state, no_state_status = actions.step_heading_state(empty_heading, direction=-1)
    last_state, last_state_status = actions.step_heading_state(done_heading, direction=1)

    assert no_state is None
    assert no_state_status == "State unchanged"
    assert last_state == "DONE"
    assert last_state_status == "Already at last state"


def test_step_heading_state_deduplicates_document_states() -> None:
    """State stepping should deduplicate repeated all_states values."""
    heading = node_from_org("#+TODO: TODO TODO WAITING | DONE DONE\n* TODO Task\n")[0]

    new_state, status = actions.step_heading_state(heading, direction=1)

    assert new_state == "WAITING"
    assert status is None


def test_apply_state_move_steps_state_and_reloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shift state move should persist, reload, and keep repeater behavior path."""
    args = make_board_args([])
    node = node_from_org("#+TODO: TODO | DONE\n* TODO Task\n")[0]
    session = _make_session(
        args=args,
        nodes=[node],
        columns=[_col("TODO", [node])],
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

    monkeypatch.setattr(actions, "_save_document_changes", _capture_save)
    monkeypatch.setattr(
        actions,
        "reload_session",
        lambda _session, preserve_identity: reloaded.append(preserve_identity),
    )

    actions.apply_state_move(session, direction=1)

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
    session = _make_session(
        args=args,
        nodes=original_nodes,
        columns=actions.build_selector_board_columns(
            original_nodes,
            actions.resolve_column_specs(args, {}),
        ),
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=1,
        scroll_offset=0,
        status_message="",
    )

    focused = session.columns[1].nodes[1]
    focused.priority = "A"
    preserve_identity = heading_locator(focused)

    reloaded_nodes = node_from_org("* TODO [#A] Other\n* TODO [#A] Focus\n")

    monkeypatch.setattr(
        actions,
        "load_and_process_data",
        lambda _args, _config: (reloaded_nodes, ["TODO"], ["DONE"]),
    )

    actions.reload_session(session, preserve_identity)

    selected = actions.selected_node(session)
    assert selected is not None
    assert selected.title_text == "Focus"


def test_edit_selected_task_in_external_editor_reports_no_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing through the shared external-editor path should report no changes."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = _make_session(
        args=args,
        nodes=nodes,
        columns=[
            _col("NOT STARTED", []),
            _col("TODO", nodes),
            _col("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )

    def _fake_edit(_heading: Heading) -> DocumentEditResult:
        return DocumentEditResult(changed=False)

    monkeypatch.setattr(actions, "edit_heading_subtree_in_external_editor", _fake_edit)

    actions.edit_selected_task_in_external_editor(session)
    assert session.status_message == "No changes."


def test_edit_selected_task_in_external_editor_reloads_with_identity_after_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changed edit should reload using the selected task identity."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = _make_session(
        args=args,
        nodes=nodes,
        columns=[
            _col("NOT STARTED", []),
            _col("TODO", nodes),
            _col("COMPLETED", []),
        ],
        color_enabled=False,
        selected_column_index=1,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    source_node = nodes[0]

    def _fake_edit(_heading: Heading) -> DocumentEditResult:
        return DocumentEditResult(changed=True)

    reloaded_identity = None

    def _capture_reload(_session: actions.BoardSession, identity: object) -> None:
        nonlocal reloaded_identity
        reloaded_identity = identity

    monkeypatch.setattr(actions, "edit_heading_subtree_in_external_editor", _fake_edit)
    monkeypatch.setattr(actions, "reload_session", _capture_reload)

    actions.edit_selected_task_in_external_editor(session)
    assert session.status_message == "Task updated"
    assert reloaded_identity == heading_locator(source_node)


def test_archive_selected_task_archives_selected_heading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Archiving the selected task should use the shared archive helper."""
    args = make_board_args([])
    nodes = node_from_org("* TODO Task\n")
    session = _make_session(
        args=args,
        nodes=nodes,
        columns=[
            _col("NOT STARTED", []),
            _col("TODO", nodes),
            _col("COMPLETED", []),
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
    ) -> ArchiveMoveResult:
        location = ArchiveLocation(
            raw_spec="%s_archive::",
            file_path="tasks.org_archive",
            parent_title=None,
        )
        target = ArchiveTarget(
            location=location,
            document=heading.document,
            parent_heading=None,
        )
        return ArchiveMoveResult(
            heading=heading,
            target=target,
            source_document=heading.document,
            destination_document=heading.document,
        )

    monkeypatch.setattr(actions, "archive_heading_subtree_and_save", _fake_archive)
    monkeypatch.setattr(actions, "reload_session", lambda _session, _identity: None)

    actions.archive_selected_task(session)
    assert session.status_message == "Task archived"


def test_run_board_does_not_hide_unknown_or_empty_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown and empty task states should still be visible on the board."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], width=120)

    monkeypatch.setattr(sys, "argv", ["org", "board"])
    output = _render_board_output(args)

    assert "Task without any state" in output
    assert "WAITING Custom todo state" in output


def test_run_board_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should print No results when filters remove all tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "board", "--filter-tag", "nomatch$"])
    output = _render_board_output(args)

    assert output.strip() == "No results"


def test_run_board_rejects_width_below_80(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should reject console widths below the minimum."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], width=79)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "79"])
    with pytest.raises(typer.BadParameter, match="--width must be at least 80"):
        board_command.run_board(args, _app_config())


def test_run_board_limit_applies_before_grouping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should respect --limit when selecting processed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=1)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--limit", "1"])
    output = _render_board_output(args)

    assert "Refactor codebase" in output
    assert "Fix bug in parser" not in output


def test_run_board_offset_applies_before_grouping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should respect --offset when selecting processed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=1, offset=1, days=100000)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--offset", "1", "--limit", "1"])
    output = _render_board_output(args)

    assert "Refactor codebase" not in output
    assert "Fix bug in parser" in output


def test_run_board_negative_max_results_raises_bad_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should reject negative --limit values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=-1)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--limit", "-1"])
    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        board_command.run_board(args, _app_config())


def test_run_board_negative_offset_raises_bad_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should reject negative --offset values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], offset=-1)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--offset", "-1"])
    with pytest.raises(typer.BadParameter, match="--offset must be non-negative"):
        board_command.run_board(args, _app_config())


def test_run_board_zero_days_raises_bad_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should reject zero-day completed task windows."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], days=0)

    monkeypatch.setattr(sys, "argv", ["org", "board", "--days", "0"])
    with pytest.raises(typer.BadParameter, match="--days must be at least 1"):
        board_command.run_board(args, _app_config())


def test_run_board_uses_pager_when_render_exceeds_console_height(
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

    args = make_board_args([fixture_path], max_results=None)
    config = _app_config()
    args.max_results = board_command._resolve_tasks_limit(args.max_results)
    nodes, discovered_todo_states, discovered_done_states = load_and_process_data(
        args,
        config,
    )
    nodes = actions.filter_recent_completed_nodes(nodes, args.days)
    todo_states, done_states = actions.resolved_states(
        args,
        discovered_todo_states,
        discovered_done_states,
    )
    columns = actions.build_selector_board_columns(nodes, actions.resolve_column_specs(args, {}))
    ui.render_static_board(
        console,
        columns,
        done_states=done_states,
        todo_states=todo_states,
        color_enabled=False,
    )

    assert pager_called["value"]


def test_run_board_selector_uses_full_nodes_from_multiple_files(
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
    config = _app_config(
        board_views={
            "kanban": org.config.app.BoardViewConfig(
                name="kanban",
                columns=[
                    org.config.app.BoardColumnConfig(name="TODO", filter='str(.todo) == "TODO"'),
                ],
            ),
        },
    )
    monkeypatch.setattr(sys, "argv", ["org", "board", "--view", "kanban", "--width", "160"])
    output = _render_board_output_with_config(args, config)
    assert "First file task" in output
    assert "Second file task" in output


def test_run_board_coalesce_completed_true_shows_completed_column(
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
    output = _render_board_output(args)

    assert "DONE" in output
    assert "Completed task" in output


def test_run_board_coalesce_completed_true_prefixes_state_in_panel(
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
    output = _render_board_output(args)

    assert "Completed task" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_run_board_coalesce_completed_false_shows_individual_done_columns(
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
    output = _render_board_output(args)

    assert "COMPLETED" not in output
    assert "DONE" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_run_board_coalesce_completed_false_done_columns_ordered_after_todo_columns(
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
    output = _render_board_output(args)

    pos_in_progress = output.find("TODO")
    pos_done = output.find("DONE")

    assert pos_in_progress != -1
    assert pos_done != -1
    assert pos_in_progress < pos_done


def test_run_board_coalesce_completed_false_tasks_in_correct_columns(
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
    output = _render_board_output(args)

    assert "Completed task" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_run_board_uses_configured_view_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requested configured view should render configured columns."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], view="kanban", width=150)
    config = _app_config(board_views=_board_views_configured())
    monkeypatch.setattr(sys, "argv", ["org", "board", "--view", "kanban", "--width", "150"])
    output = _render_board_output_with_config(args, config)
    assert "Backlog" in output
    assert "Working" in output


def test_run_board_missing_requested_view_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing requested view should return explicit BadParameter."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="missing")
    config = _app_config(
        board_views={
            "other": org.config.app.BoardViewConfig(
                name="other",
                columns=[
                    org.config.app.BoardColumnConfig(name="TODO", filter='.todo == "TODO"'),
                ],
            ),
        },
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    with pytest.raises(typer.BadParameter, match="Requested board view not found"):
        board_command.run_board(args, config)


def test_run_board_requested_view_without_configured_views_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit --view should fail when no configured views exist."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    with pytest.raises(typer.BadParameter, match="no board views are configured"):
        board_command.run_board(args, _app_config(board_views={}))


def test_run_board_uses_default_view_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config-defaulted view value should drive board view resolution."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], view=None, width=150)
    config = _app_config(board_views=_board_views_configured())
    args.view = "kanban"
    specs = actions.resolve_column_specs(args, config.board.views)
    assert [spec.name for spec in specs] == ["Backlog", "Working"]
    monkeypatch.setattr(sys, "argv", ["org", "board", "--width", "150"])
    output = _render_board_output_with_config(args, config)
    assert "Backlog" in output


def test_run_board_invalid_filter_or_order_by_parse_error_has_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter/order-by parse failures should include view and column context."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    config = _app_config(
        board_views={
            "kanban": org.config.app.BoardViewConfig(
                name="kanban",
                columns=[
                    org.config.app.BoardColumnConfig(name="Broken", filter=".todo =="),
                ],
            ),
        },
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    with pytest.raises(typer.BadParameter, match="view=kanban, column=Broken"):
        board_command.run_board(args, config)


def test_run_board_invalid_filter_or_order_by_runtime_error_has_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter/order-by runtime failures should include view and column context."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    config = _app_config(
        board_views={
            "kanban": org.config.app.BoardViewConfig(
                name="kanban",
                columns=[
                    org.config.app.BoardColumnConfig(
                        name="Broken",
                        filter="unknown_fn(.todo)",
                    ),
                ],
            ),
        },
    )
    monkeypatch.setattr(
        board_command,
        "load_and_process_data",
        lambda _args, _config: ([node_from_org("* TODO Task\n")[0]], ["TODO"], ["DONE"]),
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    with pytest.raises(typer.BadParameter, match="view=kanban, column=Broken"):
        board_command.run_board(args, config)


def test_run_board_invalid_order_by_parse_error_has_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid order-by parse should include view and column context."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], view="kanban")
    config = _app_config(
        board_views={
            "kanban": org.config.app.BoardViewConfig(
                name="kanban",
                columns=[
                    org.config.app.BoardColumnConfig(
                        name="Broken",
                        filter='.todo == "TODO"',
                        order_by=".priority ==",
                    ),
                ],
            ),
        },
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    with pytest.raises(
        typer.BadParameter,
        match=r"Invalid board filter/order-by \(view=kanban, column=Broken\)",
    ):
        board_command.run_board(args, config)


def test_apply_state_move_reload_reassigns_task_across_selector_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State changes should reload and move task to new selector column."""
    args = make_board_args([], view="kanban", days=100000)
    source_node = node_from_org("#+TODO: TODO | DONE\n* TODO Task\n")[0]
    config = _app_config(
        board_views={
            "kanban": org.config.app.BoardViewConfig(
                name="kanban",
                columns=[
                    org.config.app.BoardColumnConfig(name="TODO", filter='.todo == "TODO"'),
                    org.config.app.BoardColumnConfig(name="DONE", filter='.todo == "DONE"'),
                ],
            ),
        },
    )

    session = _make_session(
        args=args,
        nodes=[source_node],
        app_config=config,
        columns=actions.build_selector_board_columns(
            [source_node],
            actions.resolve_column_specs(args, config.board.views),
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
        _config: org.config.app.AppConfig,
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

    monkeypatch.setattr(actions, "_save_document_changes", _capture_save)
    monkeypatch.setattr(actions, "load_and_process_data", _load_after_change)

    actions.apply_state_move(session, direction=1)
    assert saved_documents == [source_node.document]
    assert session.selected_column_index == 1
    selected = actions.selected_node(session)
    assert selected is not None
    assert selected.todo == "DONE"


def test_build_task_panel_renders_rich_title_content() -> None:
    """Flow board panels should render heading RichText with Rich styles."""
    nodes = node_from_org(
        (
            "* TODO *Bold* /Italic/ _Underline_ +Strike+ =Verbatim= ~InlineCode~ "
            "[[https://example.com/docs][Docs]] x^{2} H_{2}O src_python{1+1} "
            "call_fn(1)\n"
        ),
    )

    panel = ui.build_task_panel(
        nodes[0],
        ui.BoardPanelRenderConfig(
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


def test_run_board_renders_rich_title_plain_output(
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
    output = _render_board_output(args)

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

    panel = ui.build_task_panel(
        node,
        ui.BoardPanelRenderConfig(
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

    panel = ui.build_task_panel(
        node,
        ui.BoardPanelRenderConfig(
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
