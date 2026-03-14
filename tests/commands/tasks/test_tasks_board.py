"""Tests for tasks board command."""

from __future__ import annotations

import os
import sys

import pytest
import typer

from org.commands.tasks import board as tasks_board


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
        todo_keys="TODO",
        done_keys="DONE",
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
        order_by_level=False,
        order_by_file_order=False,
        order_by_file_order_reversed=False,
        order_by_priority=False,
        order_by_timestamp_asc=False,
        order_by_timestamp_desc=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_board_renders_expected_columns(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Board should render NOT STARTED, todo columns, and COMPLETED."""
    fixture_path = os.path.join(FIXTURES_DIR, "custom_states.org")
    args = make_board_args(
        [fixture_path],
        todo_keys="TODO,WAITING,IN-PROGRESS",
        done_keys="DONE,CANCELLED,ARCHIVED",
        width=150,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "org",
            "tasks",
            "board",
            "--todo-keys",
            "TODO,WAITING,IN-PROGRESS",
            "--done-keys",
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
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
