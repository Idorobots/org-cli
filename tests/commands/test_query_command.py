"""Tests for query command behavior and output formatting."""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from org.cli import app
from org.commands.query import QueryArgs, run_query


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


@pytest.mark.parametrize("removed_option", ["--filter-tag", "--order-by", "--with-gamify-category"])
def test_query_removed_cli_options_are_rejected(removed_option: str) -> None:
    """Query command should reject removed filter/order/enrichment options."""
    runner = CliRunner()
    fixture_path = str(os.path.join(FIXTURES_DIR, "multiple_tags.org"))

    args = ["query", ".[]", removed_option]
    if removed_option in {"--filter-tag", "--order-by"}:
        args.append("x")
    args.append(fixture_path)

    result = runner.invoke(app, args)

    assert result.exit_code != 0
    assert "No such option" in (result.output or result.stderr)


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


def test_query_runtime_error_is_reported_as_usage_error() -> None:
    """Runtime query failures should be shown as usage errors."""
    runner = CliRunner()
    fixture_path = str(os.path.join(FIXTURES_DIR, "multiple_tags.org"))

    result = runner.invoke(app, ["query", "1 / 0", fixture_path])

    assert result.exit_code != 0
    assert "Division by zero" in (result.output or result.stderr)
