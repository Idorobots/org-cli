"""Tests for tasks query command behavior and output formatting."""

from __future__ import annotations

import json
import os

import click
import pytest
from org_parser.element import Repeat
from org_parser.text import RichText
from org_parser.time import Clock, Timestamp
from typer.testing import CliRunner

from org.cli import app
from org.commands.tasks.query import TasksQueryArgs, _is_org_object, run_tasks_query
from org.output_format import OutputFormat, OutputFormatError


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _make_args(files: list[str], query: str, **overrides: object) -> TasksQueryArgs:
    args = TasksQueryArgs(
        query=query,
        files=files,
        config=".org-cli.yaml",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_states="TODO",
        done_states="DONE",
        color_flag=False,
        width=None,
        max_results=10,
        offset=0,
        out=OutputFormat.ORG,
        out_theme="github-dark",
        pandoc_args=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_query_starts_from_root_nodes(capsys: pytest.CaptureFixture[str]) -> None:
    """Query should treat loaded root nodes as the initial stream."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | length")

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "3"


def test_run_query_org_node_results_render_with_file_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Org node query results should render like detailed task output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[0]")

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert f"# {fixture_path}" in captured
    assert "No results" not in captured


def test_run_query_org_root_results_render_with_file_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Org root query results should render as org syntax blocks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]")

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert f"# {fixture_path}" in captured
    assert "No results" not in captured


def test_run_query_default_org_uses_plain_formatter_for_string_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default org output should print plain lines for string-only results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[] | .title_text")

    def _fake_compiled_query(_stream: object, _context: object) -> list[object]:
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "org.commands.tasks.query.compile_query_text",
        lambda _query: _fake_compiled_query,
    )
    monkeypatch.setattr(
        "org.commands.tasks.query.load_root_data",
        lambda _args: ([], ["TODO"], ["DONE"]),
    )

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.splitlines() == ["alpha", "beta"]


def test_run_query_default_org_uses_json_formatter_for_mixed_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default org output should fall back to JSON for mixed-type results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]")

    def _fake_compiled_query(_stream: object, _context: object) -> list[object]:
        return ["alpha", 1, None]

    monkeypatch.setattr(
        "org.commands.tasks.query.compile_query_text",
        lambda _query: _fake_compiled_query,
    )
    monkeypatch.setattr(
        "org.commands.tasks.query.load_root_data",
        lambda _args: ([], ["TODO"], ["DONE"]),
    )

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert json.loads(captured) == ["alpha", 1, None]


def test_run_query_default_org_uses_json_formatter_for_none_result(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default org output should print JSON null for non-org None results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]")

    def _fake_compiled_query(_stream: object, _context: object) -> list[object]:
        return [None]

    monkeypatch.setattr(
        "org.commands.tasks.query.compile_query_text",
        lambda _query: _fake_compiled_query,
    )
    monkeypatch.setattr(
        "org.commands.tasks.query.load_root_data",
        lambda _args: ([], ["TODO"], ["DONE"]),
    )

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert json.loads(captured) is None


def test_query_syntax_error_shows_pointer_without_invalid_value_prefix() -> None:
    """Query syntax errors should include pointer and omit Invalid value prefix."""
    runner = CliRunner()
    fixture_path = str(os.path.join(FIXTURES_DIR, "multiple_tags.org"))

    result = runner.invoke(
        app,
        ["tasks", "query", ".[][] | select(not(.todo in $done_states) | .todo", fixture_path],
    )

    assert result.exit_code != 0
    assert "Invalid query syntax:" in result.output
    assert "Invalid value:" not in result.output
    assert ".[][] | select(not(.todo in $done_states) | .todo" in result.output
    assert "^" in result.output


def test_query_empty_scheduled_timestamp_renders_json_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Querying an unset scheduled timestamp should render as JSON null."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    args = _make_args([fixture_path], ".[][].scheduled")

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "null"


def test_query_empty_org_result_set_prints_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    """Empty org-object result sets should print No results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | select(false)")

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_run_query_negative_max_results_raises_bad_parameter() -> None:
    """Query should reject negative limit values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]", max_results=-1)

    with pytest.raises(click.BadParameter, match="--limit must be non-negative"):
        run_tasks_query(args)


def test_query_runtime_error_is_reported_as_usage_error() -> None:
    """Runtime query failures should be shown as usage errors."""
    runner = CliRunner()
    fixture_path = str(os.path.join(FIXTURES_DIR, "multiple_tags.org"))

    result = runner.invoke(app, ["tasks", "query", "1 / 0", fixture_path])

    assert result.exit_code != 0
    assert "Division by zero" in (result.output or result.stderr)


def test_run_query_markdown_converts_org_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markdown query formatter should invoke pandoc with markdown output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[]", out="markdown")
    seen: dict[str, object] = {}

    def _fake_pandoc(org_text: str, output_format: str, pandoc_args: list[str]) -> str:
        seen["org_text"] = org_text
        seen["output_format"] = output_format
        seen["pandoc_args"] = pandoc_args
        return "converted markdown"

    monkeypatch.setattr("org.commands.tasks.query._org_to_pandoc_format", _fake_pandoc)
    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "converted markdown"
    assert seen["output_format"] == "markdown"
    assert seen["pandoc_args"] == []
    assert "Refactor codebase" in str(seen["org_text"])


def test_run_query_markdown_converts_scalar_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markdown query formatter should pass scalar outputs to pandoc."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | length", out="markdown")
    seen: dict[str, object] = {}

    def _fake_pandoc(org_text: str, output_format: str, pandoc_args: list[str]) -> str:
        seen["org_text"] = org_text
        seen["output_format"] = output_format
        seen["pandoc_args"] = pandoc_args
        return "converted scalar"

    monkeypatch.setattr("org.commands.tasks.query._org_to_pandoc_format", _fake_pandoc)
    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "converted scalar"
    assert seen["org_text"] == "3"
    assert seen["output_format"] == "markdown"
    assert seen["pandoc_args"] == []


def test_run_query_accepts_arbitrary_pandoc_output_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Query should route non-org/json --out values through pandoc."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args(
        [fixture_path],
        ".[] | .children | .[]",
        out="gfm",
        pandoc_args="--wrap=none",
    )

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip()
    assert "Refactor codebase" in captured


def test_run_query_markdown_pandoc_error_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Markdown formatter failures should be surfaced as CLI usage errors."""

    class _FailingFormatter:
        include_filenames = False

        def prepare(
            self,
            values: list[object],
            console: object,
            color_enabled: bool,
            out_theme: str,
        ) -> object:
            del values
            del console
            del color_enabled
            del out_theme
            raise OutputFormatError("pandoc missing")

    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]", out="markdown")
    monkeypatch.setattr(
        "org.commands.tasks.query.get_query_formatter",
        lambda _out, _pandoc_args: _FailingFormatter(),
    )

    with pytest.raises(click.UsageError, match="pandoc missing"):
        run_tasks_query(args)


def test_run_query_pandoc_empty_results_prints_no_results(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandoc query output should preserve empty-result messaging."""

    def _should_not_call(_org_text: str, _output_format: str, _pandoc_args: list[str]) -> str:
        raise AssertionError("pandoc must not be called for empty results")

    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args(
        [fixture_path],
        ".[] | .children | .[] | select(false)",
        out="gfm",
    )
    monkeypatch.setattr("org.commands.tasks.query._org_to_pandoc_format", _should_not_call)

    run_tasks_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_run_query_json_root_result_is_single_object(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON query output should return one object for a single root result."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]", out=OutputFormat.JSON)

    run_tasks_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, dict)
    assert parsed["type"] == "Document"
    assert "filename" in parsed
    assert "todo_states" in parsed


def test_run_query_json_node_result_excludes_env(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON query output should exclude env from non-root org nodes."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[0]", out=OutputFormat.JSON)

    run_tasks_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, dict)
    assert parsed["type"] == "Heading"
    assert "env" not in parsed


def test_run_query_json_scalars_emit_single_json_value(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON query output should emit scalar JSON when one item remains."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | length", out=OutputFormat.JSON)

    run_tasks_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert parsed == 3


def test_run_query_json_preserves_multiple_collection_results(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Query should not drop later collection results from the stream."""
    fixture_paths = [
        os.path.join(FIXTURES_DIR, "multiple_tags.org"),
        os.path.join(FIXTURES_DIR, "simple.org"),
    ]
    args = _make_args(fixture_paths, ".[] | .children", out=OutputFormat.JSON)

    run_tasks_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert all(isinstance(item, list) for item in parsed)


def test_is_org_object_supports_org_parser_text_and_element_types() -> None:
    """Org formatter detection should include rich text and element values."""
    timestamp = Timestamp.from_source("<2025-01-02 Thu>")
    clock = Clock(timestamp=Timestamp.from_source("<2025-01-02 Thu 10:00-11:00>"))
    repeat = Repeat(
        before="TODO",
        after="DONE",
        timestamp=Timestamp.from_source("<2025-01-02 Thu>"),
    )

    assert _is_org_object(timestamp)
    assert _is_org_object(clock)
    assert _is_org_object(repeat)
    assert _is_org_object(RichText("text"))
    assert not _is_org_object({"key": "value"})


def test_run_query_invalid_pandoc_args_is_usage_error() -> None:
    """Malformed pandoc args should be surfaced as a CLI usage error."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]", out="gfm", pandoc_args='"')

    with pytest.raises(click.UsageError, match="No closing quotation"):
        run_tasks_query(args)
