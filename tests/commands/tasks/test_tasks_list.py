"""Tests for tasks list command."""

from __future__ import annotations

import json
import os
import sys

import click
import pytest

from org.commands.tasks import list as tasks_list
from org.output_format import OutputFormat, OutputFormatError


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
        max_results=10,
        details=False,
        offset=0,
        order_by="timestamp-desc",
        with_numeric_gamify_exp=False,
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
        buckets=50,
        out=OutputFormat.ORG,
        out_theme="github-dark",
        pandoc_args=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


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
    args = make_list_args([fixture_path], max_results=2, buckets=0)

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
    args = make_list_args([fixture_path], max_results=1, offset=1, buckets=0)

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


def test_run_tasks_list_markdown_converts_nodes_to_single_document(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
    assert parsed[0]["type"] == "OrgNode"
    assert "env" not in parsed[0]


def test_run_tasks_list_json_emits_single_value_for_single_node(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSON tasks output should be one object when one task remains."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON, max_results=1)

    monkeypatch.setattr(sys, "argv", ["org", "tasks", "list", "--out", "json", "-n", "1"])
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, dict)
    assert parsed["type"] == "OrgNode"


def test_run_tasks_list_json_no_results_emits_empty_array(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSON tasks output should emit an empty array when no tasks match."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_list_args([fixture_path], out=OutputFormat.JSON, filter_tags=["nomatch$"])

    monkeypatch.setattr(
        sys, "argv", ["org", "tasks", "list", "--out", "json", "--filter-tag", "nomatch$"]
    )
    tasks_list.run_tasks_list(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert parsed == []


def test_run_tasks_list_json_max_results_zero_emits_empty_array(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
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
