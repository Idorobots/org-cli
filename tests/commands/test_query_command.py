"""Tests for query command behavior and output formatting."""

from __future__ import annotations

import json
import os

import click
import pytest
from typer.testing import CliRunner

from org.cli import app
from org.commands.query import QueryArgs, run_query
from org.output_format import OutputFormat, OutputFormatError


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _make_args(files: list[str], query: str, **overrides: object) -> QueryArgs:
    args = QueryArgs(
        query=query,
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
        color_flag=False,
        max_results=10,
        offset=0,
        out=OutputFormat.ORG,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_query_starts_from_root_nodes(capsys: pytest.CaptureFixture[str]) -> None:
    """Query should treat loaded root nodes as the initial stream."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | length")

    run_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "3"


def test_run_query_org_node_results_render_with_file_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Org node query results should render like detailed task output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[0]")

    run_query(args)
    captured = capsys.readouterr().out

    assert f"# {fixture_path}" in captured
    assert "No results" not in captured


def test_run_query_org_root_results_render_with_file_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Org root query results should render as org syntax blocks."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]")

    run_query(args)
    captured = capsys.readouterr().out

    assert f"# {fixture_path}" in captured
    assert "No results" not in captured


def test_query_syntax_error_shows_pointer_without_invalid_value_prefix() -> None:
    """Query syntax errors should include pointer and omit Invalid value prefix."""
    runner = CliRunner()
    fixture_path = str(os.path.join(FIXTURES_DIR, "multiple_tags.org"))

    result = runner.invoke(
        app,
        ["query", ".[][] | select(not(.todo in $done_keys) | .todo", fixture_path],
    )

    assert result.exit_code != 0
    assert "Invalid query syntax:" in result.output
    assert "Invalid value:" not in result.output
    assert ".[][] | select(not(.todo in $done_keys) | .todo" in result.output
    assert "^" in result.output


def test_query_empty_scheduled_timestamp_renders_none(capsys: pytest.CaptureFixture[str]) -> None:
    """Querying an unset scheduled timestamp should render as none."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    args = _make_args([fixture_path], ".[][].scheduled")

    run_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "none"


def test_query_empty_org_result_set_prints_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    """Empty org-object result sets should print No results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | select(false)")

    run_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "No results"


def test_query_runtime_error_is_reported_as_usage_error() -> None:
    """Runtime query failures should be shown as usage errors."""
    runner = CliRunner()
    fixture_path = str(os.path.join(FIXTURES_DIR, "multiple_tags.org"))

    result = runner.invoke(app, ["query", "1 / 0", fixture_path])

    assert result.exit_code != 0
    assert "Division by zero" in (result.output or result.stderr)


def test_run_query_markdown_converts_org_results(capsys: pytest.CaptureFixture[str]) -> None:
    """Markdown query formatter should convert org nodes into markdown."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[]", out=OutputFormat.MD)

    run_query(args)
    captured = capsys.readouterr().out

    assert captured.strip()
    assert "Refactor codebase" in captured


def test_run_query_markdown_converts_scalar_results(capsys: pytest.CaptureFixture[str]) -> None:
    """Markdown query formatter should emit valid markdown for scalar outputs."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | length", out=OutputFormat.MD)

    run_query(args)
    captured = capsys.readouterr().out

    assert captured.strip() == "3"


def test_run_query_markdown_pandoc_error_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Markdown formatter failures should be surfaced as CLI usage errors."""

    class _FailingFormatter:
        include_filenames = False

        def render(self, values: list[object], console: object, color_enabled: bool) -> None:
            del values
            del console
            del color_enabled
            raise OutputFormatError("pandoc missing")

    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]", out=OutputFormat.MD)
    monkeypatch.setattr("org.commands.query.get_query_formatter", lambda _out: _FailingFormatter())

    with pytest.raises(click.UsageError, match="pandoc missing"):
        run_query(args)


def test_run_query_json_root_result_is_single_object(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON query output should return one object for a single root result."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[]", out=OutputFormat.JSON)

    run_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, dict)
    assert parsed["type"] == "OrgRootNode"
    assert "env" in parsed


def test_run_query_json_node_result_excludes_env(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON query output should exclude env from non-root org nodes."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | .[0]", out=OutputFormat.JSON)

    run_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert isinstance(parsed, dict)
    assert parsed["type"] == "OrgNode"
    assert "env" not in parsed


def test_run_query_json_scalars_emit_single_json_value(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON query output should emit scalar JSON when one item remains."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = _make_args([fixture_path], ".[] | .children | length", out=OutputFormat.JSON)

    run_query(args)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert parsed == 3
