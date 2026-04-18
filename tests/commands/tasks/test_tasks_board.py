"""Tests for tasks board command."""

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

from org.commands.tasks import board as tasks_board
from tests.conftest import node_from_org


if TYPE_CHECKING:
    from collections.abc import Iterator


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def make_board_args(files: list[str], **overrides: object) -> tasks_board.BoardArgs:
    """Build BoardArgs with defaults and overrides."""
    args = tasks_board.BoardArgs(
        files=files,
        config=".org-cli.json",
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


def test_run_tasks_board_renders_expected_columns(
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
            "tasks",
            "board",
            "--todo-states",
            "TODO,WAITING,IN-PROGRESS",
            "--done-states",
            "DONE,CANCELLED,ARCHIVED",
            "--width",
            "150",
        ],
    )
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "NOT STARTED" in output
    assert "TODO" in output
    assert "WAITING" in output
    assert "IN-PROGRESS" in output
    assert "COMPLETED" in output


def test_run_tasks_board_preserves_order_in_column(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should keep per-column order from filtered/ordered task list."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args(
        [fixture_path],
        width=120,
        order_by_file_order=True,
    )

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--order-by-file-order"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    first = output.find("Refactor codebase")
    second = output.find("Fix bug in parser")
    assert first != -1
    assert second != -1
    assert first < second


def test_run_tasks_board_does_not_hide_unknown_or_empty_states(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown and empty task states should still be visible on the board."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args([fixture_path], width=120)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "Task without any state" in output
    assert "WAITING Custom todo state" in output


def test_run_tasks_board_no_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should print No results when filters remove all tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--filter-tag", "nomatch$"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert output.strip() == "No results"


def test_run_tasks_board_rejects_width_below_80(monkeypatch: pytest.MonkeyPatch) -> None:
    """Board should reject console widths below the minimum."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], width=79)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--width", "79"])
    with pytest.raises(typer.BadParameter, match="--width must be at least 80"):
        tasks_board.run_tasks_board(args)


def test_run_tasks_board_limit_applies_before_grouping(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should respect --limit when selecting processed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--limit", "1"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "Refactor codebase" in output
    assert "Fix bug in parser" not in output


def test_run_tasks_board_offset_applies_before_grouping(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should respect --offset when selecting processed tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=1, offset=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--offset", "1", "--limit", "1"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "Refactor codebase" not in output
    assert "Fix bug in parser" in output


def test_run_tasks_board_negative_max_results_raises_bad_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should reject negative --limit values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], max_results=-1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--limit", "-1"])
    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        tasks_board.run_tasks_board(args)


def test_run_tasks_board_negative_offset_raises_bad_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Board should reject negative --offset values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_board_args([fixture_path], offset=-1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--offset", "-1"])
    with pytest.raises(typer.BadParameter, match="--offset must be non-negative"):
        tasks_board.run_tasks_board(args)


def test_run_tasks_board_uses_pager_when_render_exceeds_console_height(
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
    monkeypatch.setattr("org.commands.tasks.board.build_console", lambda _color, _width: console)

    args = make_board_args([fixture_path], max_results=None)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board"])
    tasks_board.run_tasks_board(args)

    assert pager_called["value"]


def test_run_tasks_board_coalesce_completed_true_shows_completed_column(
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

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--width", "200"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "COMPLETED" in output
    assert "DONE" not in output.split("COMPLETED")[0].replace("NOT STARTED", "")
    assert "CANCELLED" not in output.split("COMPLETED")[0].replace("NOT STARTED", "")
    assert "ARCHIVED" not in output.split("COMPLETED")[0].replace("NOT STARTED", "")


def test_run_tasks_board_coalesce_completed_true_prefixes_state_in_panel(
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

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--width", "200"])
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "DONE Completed task" in output
    assert "CANCELLED Custom done state" in output
    assert "ARCHIVED Another done state" in output


def test_run_tasks_board_coalesce_completed_false_shows_individual_done_columns(
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
        ["org", "tasks", "board", "--no-coalesce-completed", "--width", "200"],
    )
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "COMPLETED" not in output
    assert "DONE" in output
    assert "CANCELLED" in output
    assert "ARCHIVED" in output


def test_run_tasks_board_coalesce_completed_false_done_columns_ordered_after_todo_columns(
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
        ["org", "tasks", "board", "--no-coalesce-completed", "--width", "200"],
    )
    tasks_board.run_tasks_board(args)
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


def test_run_tasks_board_coalesce_completed_false_tasks_in_correct_columns(
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
        ["org", "tasks", "board", "--no-coalesce-completed", "--width", "200"],
    )
    tasks_board.run_tasks_board(args)
    output = capsys.readouterr().out

    assert "Completed task" in output
    assert "Custom done state" in output
    assert "Another done state" in output


def test_build_task_panel_renders_rich_title_content() -> None:
    """Task board panels should render heading RichText with Rich styles."""
    nodes = node_from_org(
        (
            "* TODO *Bold* /Italic/ _Underline_ +Strike+ =Verbatim= ~InlineCode~ "
            "[[https://example.com/docs][Docs]] x^{2} H_{2}O src_python{1+1} "
            "call_fn(1)\n"
        ),
    )

    panel = tasks_board._build_task_panel(
        nodes[0],
        tasks_board._PanelRenderConfig(
            width=60,
            color_enabled=True,
            done_states=["DONE"],
            todo_states=["TODO"],
            coalesce_completed=True,
        ),
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


def test_run_tasks_board_renders_rich_title_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Board command should print rich title text without org inline delimiters."""
    fixture_path = os.path.join(tmp_path, "rich_board.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO *Bold* /Italic/ _Underline_ +Strike+ =Verbatim= ~InlineCode~ "
            "[[https://example.com/docs][Docs]] x^{2} H_{2}O src_python{1+1} call_fn(1)\n",
        )

    args = make_board_args([fixture_path], width=120)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "board", "--width", "120"])
    tasks_board.run_tasks_board(args)
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
