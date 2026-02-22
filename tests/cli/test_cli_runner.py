"""CliRunner tests for the Typer CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

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
