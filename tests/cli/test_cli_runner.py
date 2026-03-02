"""CliRunner tests for the Typer CLI."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from org import config
from org.cli import app


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_cli_runner_summary() -> None:
    """CliRunner should execute stats summary."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["stats", "summary", "--no-color", fixture_path])

    assert result.exit_code == 0
    assert "Total tasks:" in result.stdout


def test_cli_runner_tags_show() -> None:
    """CliRunner should filter tags with --show."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["stats", "tags", "--no-color", "--show", "Test", fixture_path])

    assert result.exit_code == 0
    assert "Test" in result.stdout
    assert "Debugging" not in result.stdout


def test_cli_runner_groups_explicit() -> None:
    """CliRunner should render explicit groups."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "tag_groups_test.org").resolve())

    result = runner.invoke(
        app,
        [
            "stats",
            "groups",
            "--no-color",
            "--group",
            "python,programming",
            fixture_path,
        ],
    )

    assert result.exit_code == 0
    assert "python, programming" in result.stdout


def test_cli_runner_tasks_list_custom_filter_without_arg() -> None:
    """Custom filter switches should not be parsed as FILE arguments."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())
    original_filters = dict(config.CONFIG_CUSTOM_FILTERS)

    try:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update({"has-todo": "select(.todo != none)"})

        result = runner.invoke(
            app,
            ["tasks", "list", "--no-color", "--filter-has-todo", fixture_path],
        )

        assert result.exit_code == 0
        assert "Refactor codebase" in result.stdout
    finally:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_filters)


def test_cli_runner_tasks_list_custom_filter_with_arg() -> None:
    """Custom filter argument value should not be parsed as FILE argument."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())
    original_filters = dict(config.CONFIG_CUSTOM_FILTERS)

    try:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update({"level-above": "select(.level > $arg)"})

        result = runner.invoke(
            app,
            ["tasks", "list", "--no-color", "--filter-level-above", "0", fixture_path],
        )

        assert result.exit_code == 0
        assert "Refactor codebase" in result.stdout
    finally:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_filters)


def test_cli_runner_tasks_list_custom_filter_required_arg_error() -> None:
    """Custom filters with $arg should fail when the argument is missing."""
    runner = CliRunner()
    original_filters = dict(config.CONFIG_CUSTOM_FILTERS)

    try:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update({"level-above": "select(.level > $arg)"})

        result = runner.invoke(
            app,
            ["tasks", "list", "--no-color", "--filter-level-above"],
        )

        assert result.exit_code != 0
        # FIXME This is only required on CI for some reason.
        combined_output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
        assert "--filter-level-above requires exactly one argument" in combined_output
    finally:
        config.CONFIG_CUSTOM_FILTERS.clear()
        config.CONFIG_CUSTOM_FILTERS.update(original_filters)
