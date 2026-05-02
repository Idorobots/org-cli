"""Tests for tasks list command."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from io import StringIO
from typing import TYPE_CHECKING

import click
import pytest
import typer
from rich.console import Console

from org.commands import editor as editor_command
from org.commands.tasks import list as tasks_list
from org.histogram import visual_len
from org.output_format import OutputFormat, OutputFormatError
from tests.conftest import node_from_org


if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from org_parser.document import Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def make_list_args(files: list[str], **overrides: object) -> tasks_list.ListArgs:
    """Build ListArgs with defaults and overrides."""
    args = tasks_list.ListArgs(
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
        width=None,
        max_results=10,
        details=False,
        offset=0,
        order_by_level=False,
        order_by_file_order=False,
        order_by_file_order_reversed=False,
        order_by_priority=False,
        order_by_timestamp_asc=False,
        order_by_timestamp_desc=False,
        with_tags_as_category=False,
        out=OutputFormat.ORG,
        out_theme="github-dark",
        pandoc_args=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_tasks_list_no_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tasks list should report when filters return no results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--filter-tag", "nomatch$"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_run_tasks_list_details_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tasks list should render detailed output with file headers."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], details=True, max_results=1, width=200)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--details", "--width", "200"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert fixture_path in captured
    assert "* TODO Refactor codebase" in captured


def test_run_tasks_list_short_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tasks list should render short output lines in order."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=2)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    filename_cell = f"{fixture_path[:15]:15s}"
    assert lines[0].startswith(f"{filename_cell}* TODO Refactor codebase")
    assert lines[0].endswith(":Maintenance:")
    assert lines[1].startswith(f"{filename_cell}* DONE Fix bug in parser")
    assert lines[1].endswith(":Debugging:SysAdmin:")


def test_run_tasks_list_offset_applied(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tasks list should apply offset before max results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=1, offset=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--offset", "1"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    filename_cell = f"{fixture_path[:15]:15s}"
    assert lines[0].startswith(f"{filename_cell}* DONE Fix bug in parser")
    assert lines[0].endswith(":Debugging:SysAdmin:")


def test_run_tasks_list_short_output_aligns_tags_to_width(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Short list should right-align tags to configured width."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=1, width=60)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--width", "60"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    assert lines
    assert len(lines[0]) == 60
    assert lines[0].endswith(":Maintenance:")


def test_run_tasks_list_short_output_truncates_filename_and_heading_for_tags(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Short list should keep 15-column filename and truncate heading when needed."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=1, width=50)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--width", "50"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    assert lines
    line = lines[0]
    assert len(line) == 50
    assert line[15] == "*"
    assert line.endswith(":Maintenance:")


def test_run_tasks_list_offset_no_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tasks list should report no results after offset."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=10, offset=10)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--offset", "10"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_run_tasks_list_negative_max_results_raises_bad_parameter() -> None:
    """Tasks list should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        tasks_list.run_tasks_list(args)


def test_run_tasks_list_markdown_converts_nodes_to_single_document(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markdown tasks formatter should invoke pandoc with markdown output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out="markdown")
    seen: dict[str, object] = {}

    def _fake_pandoc(org_text: str, output_format: str, pandoc_args: list[str]) -> str:
        seen["org_text"] = org_text
        seen["output_format"] = output_format
        seen["pandoc_args"] = pandoc_args
        return "converted markdown"

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "markdown"])
    monkeypatch.setattr("org.commands.tasks.list._org_to_pandoc_format", _fake_pandoc)
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "converted markdown"
    assert seen["output_format"] == "markdown"
    assert seen["pandoc_args"] == []
    assert "Refactor codebase" in str(seen["org_text"])
    assert "Fix bug in parser" in str(seen["org_text"])


def test_run_tasks_list_accepts_arbitrary_pandoc_output_format(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tasks list should route non-org/json --out values through pandoc."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out="gfm", pandoc_args="--wrap=none")
    seen: dict[str, object] = {}

    def _fake_pandoc(org_text: str, output_format: str, pandoc_args: list[str]) -> str:
        seen["org_text"] = org_text
        seen["output_format"] = output_format
        seen["pandoc_args"] = pandoc_args
        return "converted gfm"

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "gfm"])
    monkeypatch.setattr("org.commands.tasks.list._org_to_pandoc_format", _fake_pandoc)
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "converted gfm"
    assert seen["output_format"] == "gfm"
    assert seen["pandoc_args"] == ["--wrap=none"]
    assert "Refactor codebase" in str(seen["org_text"])


def test_run_tasks_list_markdown_pandoc_error_is_usage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markdown formatter failures should be surfaced as CLI usage errors."""

    class _FailingFormatter:
        include_filenames = False

        def prepare(self, data: object) -> object:
            del data
            raise OutputFormatError("pandoc missing")

    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out="markdown")
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "markdown"])
    monkeypatch.setattr(
        "org.commands.tasks.list.get_tasks_list_formatter",
        lambda _out, _pandoc_args: _FailingFormatter(),
    )

    with pytest.raises(click.UsageError, match="pandoc missing"):
        tasks_list.run_tasks_list(args)


def test_run_tasks_list_pandoc_empty_results_prints_no_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc tasks output should preserve empty-result messaging."""

    def _should_not_call(_org_text: str, _output_format: str, _pandoc_args: list[str]) -> str:
        raise AssertionError("pandoc must not be called for empty results")

    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args(
        [fixture_path],
        out="gfm",
        filter_tags=["nomatch$"],
    )
    monkeypatch.setattr("org.commands.tasks.list._org_to_pandoc_format", _should_not_call)

    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_run_tasks_list_json_emits_array_for_multiple_nodes(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON tasks output should be an array when multiple tasks are present."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON, max_results=2)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "json"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["type"] == "Heading"
    assert "env" not in parsed[0]


def test_run_tasks_list_json_emits_single_value_for_single_node(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON tasks output should be one object when one task remains."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON, max_results=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "json", "-n", "1"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, dict)
    assert parsed["type"] == "Heading"


def test_run_tasks_list_json_no_results_emits_empty_array(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON tasks output should emit an empty array when no tasks match."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON, filter_tags=["nomatch$"])

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "tasks", "list", "--out", "json", "--filter-tag", "nomatch$"],
    )
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert parsed == []


def test_run_tasks_list_json_max_results_zero_emits_empty_array(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON tasks output should stay valid JSON when max results is zero."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON, max_results=0)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "json", "-n", "0"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert parsed == []


def test_run_tasks_list_invalid_pandoc_args_is_usage_error() -> None:
    """Malformed pandoc args should be surfaced as a CLI usage error."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out="gfm", pandoc_args='"')

    with pytest.raises(click.UsageError, match="No closing quotation"):
        tasks_list.run_tasks_list(args)


def test_run_tasks_list_defaults_limit_to_all_results_with_paging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tasks list should default --limit to all results and use pager on overflow."""
    fixture_path = os.path.join(tmp_path, "tasks.org")
    tasks = "\n".join(f"* TODO Task {index}" for index in range(10))
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(tasks)

    buffer = StringIO()
    console = Console(width=80, height=4, file=buffer, no_color=True, force_terminal=False)
    pager_called = {"value": False}

    @contextmanager
    def _fake_pager(*args: object, **kwargs: object) -> Iterator[None]:
        del args, kwargs
        pager_called["value"] = True
        yield

    monkeypatch.setattr(console, "pager", _fake_pager)
    monkeypatch.setattr("org.commands.tasks.list.build_console", lambda _color, _width: console)

    args = make_list_args([fixture_path], max_results=None)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list"])
    tasks_list.run_tasks_list(args)

    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert len(lines) == 10
    assert pager_called["value"]


def test_run_tasks_list_unicode_heading_aligns_tags_to_visual_width(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Short list should align tags correctly for wide unicode headings."""
    fixture_path = os.path.join(tmp_path, "unicode.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO 修正タスク名の確認 :開発:\n")

    args = make_list_args([fixture_path], max_results=1, width=60)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--width", "60"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line.strip()]
    assert lines
    assert visual_len(lines[0]) == 60
    assert lines[0].endswith(":開発:")


def test_run_tasks_list_details_wraps_long_lines_to_console_width(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Detailed list should wrap long lines to fit console width."""
    fixture_path = os.path.join(tmp_path, "details.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO This is a very long heading that should wrap around the viewport width\n",
        )

    args = make_list_args([fixture_path], details=True, width=60, max_results=1)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--details", "--width", "60"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    lines = [line for line in captured.splitlines() if line]
    assert len(lines) > 2
    assert max(len(line) for line in lines) <= 60


def test_run_tasks_list_uses_pager_for_org_output_when_overflowing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Org output should use pager when rendered lines exceed console height."""
    fixture_path = os.path.join(tmp_path, "many.org")
    tasks = "\n".join(f"* TODO Task {index}" for index in range(12))
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(tasks)

    console = Console(
        width=80,
        height=4,
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
    monkeypatch.setattr("org.commands.tasks.list.build_console", lambda _color, _width: console)

    args = make_list_args([fixture_path], max_results=12)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--limit", "12"])
    tasks_list.run_tasks_list(args)

    assert pager_called["value"]


def test_run_tasks_list_skips_pager_when_limit_below_console_height(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Org output should skip pager when requested limit is below console height."""
    fixture_path = os.path.join(tmp_path, "small-limit.org")
    tasks = "\n".join(f"* TODO Task {index}" for index in range(12))
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(tasks)

    console = Console(
        width=80,
        height=10,
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
    monkeypatch.setattr("org.commands.tasks.list.build_console", lambda _color, _width: console)

    args = make_list_args([fixture_path], max_results=3)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--limit", "3"])
    tasks_list.run_tasks_list(args)

    assert not pager_called["value"]


def test_run_tasks_list_does_not_use_pager_for_json_output_when_overflowing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Non-org output should not use pager even when output exceeds height."""
    fixture_path = os.path.join(tmp_path, "many-json.org")
    tasks = "\n".join(f"* TODO Task {index}" for index in range(12))
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(tasks)

    console = Console(
        width=80,
        height=4,
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
    monkeypatch.setattr("org.commands.tasks.list.build_console", lambda _color, _width: console)

    args = make_list_args([fixture_path], max_results=12, out=OutputFormat.JSON)
    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "json", "--limit", "12"])
    tasks_list.run_tasks_list(args)

    assert not pager_called["value"]


def test_run_tasks_list_uses_interactive_mode_when_tty_and_not_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTY execution should enter interactive mode when no blocking switches are explicit."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path])
    called = {"interactive": False}

    def _fake_interactive(
        _console: Console,
        _args: tasks_list.ListArgs,
        data: object,
    ) -> None:
        session_data = data
        called["interactive"] = True
        assert isinstance(session_data, tasks_list._TasksListSessionData)
        assert session_data.nodes
        assert session_data.todo_states
        assert session_data.done_states
        assert session_data.color_enabled is False

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(tasks_list, "_run_tasks_list_interactive", _fake_interactive)
    monkeypatch.setattr(
        tasks_list,
        "_run_tasks_list_static",
        lambda *_args, **_kwargs: pytest.fail("static mode should not be used"),
    )

    tasks_list.run_tasks_list(args)

    assert called["interactive"]


def test_run_tasks_list_details_switch_blocks_interactive_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit --details should force static rendering even in TTY mode."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], details=True)
    called = {"static": False}

    def _fake_static(
        _console: Console,
        _args: tasks_list.ListArgs,
        data: object,
    ) -> None:
        session_data = data
        called["static"] = True
        assert isinstance(session_data, tasks_list._TasksListSessionData)
        assert session_data.nodes
        assert session_data.todo_states
        assert session_data.done_states
        assert session_data.color_enabled is False

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(
        tasks_list,
        "_run_tasks_list_interactive",
        lambda *_args, **_kwargs: pytest.fail("interactive mode should be blocked by --details"),
    )
    monkeypatch.setattr(tasks_list, "_run_tasks_list_static", _fake_static)

    tasks_list.run_tasks_list(args)

    assert called["static"]


def test_run_tasks_list_out_switch_blocks_interactive_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit --out should force static rendering even in TTY mode."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON)
    called = {"static": False}

    def _fake_static(
        _console: Console,
        _args: tasks_list.ListArgs,
        data: object,
    ) -> None:
        session_data = data
        called["static"] = True
        assert isinstance(session_data, tasks_list._TasksListSessionData)
        assert session_data.nodes
        assert session_data.todo_states
        assert session_data.done_states
        assert session_data.color_enabled is False

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(
        tasks_list,
        "_run_tasks_list_interactive",
        lambda *_args, **_kwargs: pytest.fail("interactive mode should be blocked by --out"),
    )
    monkeypatch.setattr(tasks_list, "_run_tasks_list_static", _fake_static)

    tasks_list.run_tasks_list(args)

    assert called["static"]


def test_filter_nodes_by_search_matches_full_node_text() -> None:
    """Interactive search should match heading and body text from node-local contents."""
    nodes = node_from_org("* TODO Alpha title\nBody needle text\n* TODO Beta\n")

    title_matches = tasks_list._filter_nodes_by_search(nodes, "alpha")
    body_matches = tasks_list._filter_nodes_by_search(nodes, "needle")
    no_matches = tasks_list._filter_nodes_by_search(nodes, "missing")

    assert [node.title_text for node in title_matches] == ["Alpha title"]
    assert [node.title_text for node in body_matches] == ["Alpha title"]
    assert no_matches == []


def test_filter_nodes_by_search_excludes_child_subtree_text() -> None:
    """Search text should only include each node's own contents, not children text."""
    nodes = node_from_org(
        "* TODO Parent\nParent body\n** TODO Child\nUnique child text\n",
    )

    matches = tasks_list._filter_nodes_by_search(nodes, "Unique child text")

    assert [node.title_text for node in matches] == ["Child"]


def test_filter_nodes_by_search_handles_non_string_property_values() -> None:
    """Search should not fail when node properties contain non-string values."""
    nodes = node_from_org("* TODO Parent\n")
    node = nodes[0]
    node.properties["DISPLAY"] = 123

    matches = tasks_list._filter_nodes_by_search(nodes, "123")

    assert [item.title_text for item in matches] == ["Parent"]


def test_handle_interactive_key_mouse_wheel_moves_selection() -> None:
    """Mouse wheel key tokens should move interactive selection."""
    nodes = node_from_org("* TODO A\n* TODO B\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    console = Console(file=StringIO(), force_terminal=False)

    assert tasks_list._handle_interactive_key(console, session, "WHEEL-DOWN") is True
    assert session.selected_index == 1
    assert tasks_list._handle_interactive_key(console, session, "WHEEL-UP") is True
    assert session.selected_index == 0


def test_interactive_rows_counter_tracks_selected_row_while_scrolling() -> None:
    """Rows counter should follow selected row index in both directions."""
    nodes = node_from_org("* TODO A\n* TODO B\n* TODO C\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    session.selected_index = 1
    total_rows = len(session.visible_nodes)

    down_capture = StringIO()
    down_console = Console(
        file=down_capture,
        force_terminal=False,
        width=80,
        height=8,
        no_color=True,
    )
    down_console.print(tasks_list._interactive_tasks_list_renderable(down_console, session))
    assert f"Rows 2/{total_rows}" in down_capture.getvalue()

    session.selected_index = 0
    up_capture = StringIO()
    up_console = Console(file=up_capture, force_terminal=False, width=80, height=8, no_color=True)
    up_console.print(tasks_list._interactive_tasks_list_renderable(up_console, session))
    assert f"Rows 1/{total_rows}" in up_capture.getvalue()


def test_interactive_task_row_reuses_static_line_format_with_level_prefix_and_tag_alignment() -> (
    None
):
    """Interactive rows should keep static format including stars and right-aligned tags."""
    nodes = node_from_org("* TODO Task title :alpha:beta:\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )

    row = tasks_list._build_task_row_text(nodes[0], session, line_width=80)

    assert "* TODO" in row.plain
    assert row.plain.rstrip().endswith(":alpha:beta:")
    assert visual_len(row.plain) == 80


def test_interactive_task_row_parses_color_markup_without_literal_tags() -> None:
    """Interactive colored row should render markup instead of showing markup literals."""
    nodes = node_from_org("* DONE Task title\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=True,
        ),
    )

    row = tasks_list._build_task_row_text(nodes[0], session, line_width=80)

    assert "[dim white]" not in row.plain
    assert "[/]" not in row.plain


def test_handle_interactive_key_unsupported_sets_status_and_continues() -> None:
    """Unsupported key should set status message without exiting interactive mode."""
    nodes = node_from_org("* TODO A\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    console = Console(file=StringIO(), force_terminal=False)

    key = "UNSUPPORTED-ESC:1b5b3939397e"
    assert tasks_list._handle_interactive_key(console, session, key) is True
    assert session.status_message == f"Unsupported key: {key}"


def test_handle_interactive_key_enter_edits_selected_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter should trigger external-editor task editing on selected row."""
    nodes = node_from_org("* TODO A\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    console = Console(file=StringIO(), force_terminal=False)

    def _fake_edit(heading: Heading) -> editor_command.HeadingEditResult:
        return editor_command.HeadingEditResult(heading=heading, changed=False)

    monkeypatch.setattr(tasks_list, "edit_heading_subtree_in_external_editor", _fake_edit)

    assert tasks_list._handle_interactive_key(console, session, "ENTER") is True
    assert session.status_message == "No changes."


def test_apply_state_change_appends_repeat_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    """State change action should append one repeat/log transition entry."""
    nodes = node_from_org("* TODO A\n")
    node = nodes[0]
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    console = Console(file=StringIO(), force_terminal=False)
    monkeypatch.setattr(tasks_list, "_choose_state", lambda _console, _node: "DONE")
    monkeypatch.setattr(
        tasks_list,
        "_persist_and_reload_selected",
        lambda _session, _node, _status: None,
    )

    tasks_list._apply_state_change(console, session)

    assert node.todo == "DONE"
    assert node.repeats
    assert node.repeats[-1].before == "TODO"
    assert node.repeats[-1].after == "DONE"


def test_apply_scheduled_edit_updates_scheduled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scheduling edit action should update selected task scheduled timestamp."""
    nodes = node_from_org("* TODO A\n")
    node = nodes[0]
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    console = Console(file=StringIO(), force_terminal=False)
    monkeypatch.setattr(console, "input", lambda _prompt: "<2025-01-20 Mon>")
    monkeypatch.setattr(
        tasks_list,
        "_persist_and_reload_selected",
        lambda _session, _node, _status: None,
    )

    tasks_list._apply_scheduled_edit(console, session)

    assert node.scheduled is not None
    assert str(node.scheduled).startswith("<2025-01-20")


def test_apply_closed_edit_updates_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Closed edit action should update selected task closed timestamp."""
    nodes = node_from_org("* TODO A\n")
    node = nodes[0]
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )
    console = Console(file=StringIO(), force_terminal=False)
    monkeypatch.setattr(console, "input", lambda _prompt: "[2025-01-20 Mon 09:00]")
    monkeypatch.setattr(
        tasks_list,
        "_persist_and_reload_selected",
        lambda _session, _node, _status: None,
    )

    tasks_list._apply_closed_edit(console, session)

    assert node.closed is not None
    assert str(node.closed).startswith("[2025-01-20")


def test_persist_and_reload_selected_reports_save_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistence failures should be surfaced in status line and keep session alive."""
    nodes = node_from_org("* TODO A\n")
    args = make_list_args([])
    session = tasks_list._create_tasks_list_session(
        args,
        tasks_list._TasksListSessionData(
            nodes=nodes,
            todo_states=["TODO"],
            done_states=["DONE"],
            color_enabled=False,
        ),
    )

    def _raise_save(_document: object) -> None:
        raise typer.BadParameter("Permission denied for 'dummy.org'")

    monkeypatch.setattr(tasks_list, "_save_document_changes", _raise_save)

    tasks_list._persist_and_reload_selected(session, nodes[0], "updated")

    assert session.status_message == "Permission denied for 'dummy.org'"
