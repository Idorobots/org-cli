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


def test_cli_runner_tags_tag() -> None:
    """CliRunner should filter tags with --tag."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["stats", "tags", "--no-color", "--tag", "Test", fixture_path])

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
        assert "* TODO Refactor" in result.stdout
        assert ":Maintenance:" in result.stdout
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
        assert "* TODO Refactor" in result.stdout
        assert ":Maintenance:" in result.stdout
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


def test_cli_runner_allows_missing_files_when_some_exist() -> None:
    """Missing file paths should warn while command still succeeds."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())
    missing_path = str((FIXTURES_DIR / "missing.org").resolve())

    result = runner.invoke(app, ["query", ".[] | .children | length", missing_path, fixture_path])

    assert result.exit_code == 0
    assert "3" in result.stdout
    assert f"Warning: Path '{missing_path}' not found" in result.stderr


def test_cli_runner_accepts_width_override() -> None:
    """Commands should accept --width values at or above 50."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["query", "1", "--width", "50", fixture_path])

    assert result.exit_code == 0
    assert result.stdout.strip() == "1"


def test_cli_runner_rejects_width_below_minimum() -> None:
    """Commands should reject --width values below 50."""
    runner = CliRunner()
    fixture_path = str((FIXTURES_DIR / "multiple_tags.org").resolve())

    result = runner.invoke(app, ["query", "1", "--width", "49", fixture_path])

    assert result.exit_code != 0
    combined_output = result.stdout + result.stderr
    assert "Invalid value for '--width'" in combined_output
