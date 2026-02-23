"""Tests for tasks list command."""

from __future__ import annotations

import os
import sys

import pytest

from org.commands.tasks import list as tasks_list
from tests.conftest import node_from_org


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def make_list_args(files: list[str], **overrides: object) -> tasks_list.ListArgs:
    """Build ListArgs with defaults and overrides."""
    args = tasks_list.ListArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
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
        max_results=10,
        details=False,
        offset=0,
        order_by="timestamp-desc",
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_order_nodes_timestamp_sorting_missing_last() -> None:
    """Timestamp ordering should sort and push missing to the end."""
    org_text = """* DONE Task 1
CLOSED: [2024-01-10 Wed 10:00]

* DONE Task 2
CLOSED: [2024-01-12 Fri 09:00]

* TODO Task 3
"""
    nodes = node_from_org(org_text)

    desc = tasks_list.order_nodes(nodes, ["timestamp-desc"])
    asc = tasks_list.order_nodes(nodes, ["timestamp-asc"])

    assert [node.heading for node in desc] == ["Task 2", "Task 1", "Task 3"]
    assert [node.heading for node in asc] == ["Task 1", "Task 2", "Task 3"]


def test_order_nodes_gamify_exp_sorting_missing_last() -> None:
    """Gamify ordering should sort and push missing to the end."""
    org_text = """* DONE Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 20
:END:

* DONE Task 3
"""
    nodes = node_from_org(org_text)

    asc = tasks_list.order_nodes(nodes, ["gamify-exp-asc"])
    desc = tasks_list.order_nodes(nodes, ["gamify-exp-desc"])

    assert [node.heading for node in asc] == ["Task 1", "Task 2", "Task 3"]
    assert [node.heading for node in desc] == ["Task 2", "Task 1", "Task 3"]


def test_order_nodes_file_order_preserved() -> None:
    """File order should preserve input ordering."""
    org_text = """* DONE Task 1
* DONE Task 2
* DONE Task 3
"""
    nodes = node_from_org(org_text)

    ordered = tasks_list.order_nodes(nodes, ["file-order"])

    assert [node.heading for node in ordered] == ["Task 1", "Task 2", "Task 3"]


def test_order_nodes_file_order_reverse() -> None:
    """File order reverse should reverse input ordering."""
    org_text = """* DONE Task 1
* DONE Task 2
* DONE Task 3
"""
    nodes = node_from_org(org_text)

    ordered = tasks_list.order_nodes(nodes, ["file-order-reverse"])

    assert [node.heading for node in ordered] == ["Task 3", "Task 2", "Task 1"]


def test_order_nodes_level_sorting() -> None:
    """Level ordering should sort by heading level."""
    org_text = """* DONE Task 1
** DONE Task 2
*** DONE Task 3
"""
    nodes = node_from_org(org_text)

    ordered = tasks_list.order_nodes(nodes, ["level"])

    assert [node.heading for node in ordered] == ["Task 1", "Task 2", "Task 3"]


def test_order_nodes_multiple_ordering_stable() -> None:
    """Later orderings should preserve order from earlier orderings for ties."""
    org_text = """* DONE Task A
:PROPERTIES:
:gamify_exp: 10
:END:

** DONE Task B
:PROPERTIES:
:gamify_exp: 10
:END:

** DONE Task C
:PROPERTIES:
:gamify_exp: 20
:END:
"""
    nodes = node_from_org(org_text)

    ordered = tasks_list.order_nodes(nodes, ["level", "gamify-exp-asc"])

    assert [node.heading for node in ordered] == ["Task A", "Task B", "Task C"]


def test_run_tasks_list_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks list should report when filters return no results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--filter-tag", "nomatch$"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_run_tasks_list_details_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks list should render detailed output with file headers."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], details=True, max_results=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--details"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert f"# {fixture_path}" in captured
    assert "* TODO Refactor codebase" in captured


def test_run_tasks_list_short_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks list should render short output lines in order."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=2)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    assert lines[0] == f"{fixture_path}: * TODO Refactor codebase"
    assert lines[1] == f"{fixture_path}: * DONE Fix bug in parser"


def test_run_tasks_list_offset_applied(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks list should apply offset before max results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=1, offset=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--offset", "1"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    assert lines == [f"{fixture_path}: * DONE Fix bug in parser"]


def test_run_tasks_list_offset_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks list should report no results after offset."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=10, offset=10)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--offset", "10"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"
