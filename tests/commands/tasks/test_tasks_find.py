"""Tests for tasks find command."""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

from typer.testing import CliRunner

import org.config.app
from org import cli


if TYPE_CHECKING:
    from pathlib import Path


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")
EMPTY_CONFIG_PATH = os.path.join(FIXTURES_DIR, "empty-config.yaml")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
app = cli.build_app(org.config.app.AppConfig(config_path=EMPTY_CONFIG_PATH))


def _clean_output(text: str) -> str:
    """Return output text without ANSI escape sequences."""
    return ANSI_ESCAPE_RE.sub("", text)


def test_tasks_find_query_title_matches_exact_title() -> None:
    """Find should match exact title via --query-title."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(
        app,
        [
            "tasks",
            "find",
            "--query-title",
            "Refactor codebase",
            fixture_path,
        ],
    )

    assert result.exit_code == 0
    assert "Refactor codebase" in result.output
    assert "Fix bug in parser" not in result.output


def test_tasks_find_search_text_matches_full_body_text() -> None:
    """Find should match body text via full-string task rendering."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(
        app,
        ["tasks", "find", "--search-text", "Feature implementation details", fixture_path],
    )

    assert result.exit_code == 0
    assert "Implement feature A" in result.output
    assert "Refactor codebase" not in result.output


def test_tasks_find_search_pattern_matches_regex() -> None:
    """Find should regex-match against full task text."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(
        app,
        ["tasks", "find", "--search-pattern", "Feature\\s+implementation", fixture_path],
    )

    assert result.exit_code == 0
    assert "Implement feature A" in result.output
    assert "No results" not in result.output


def test_tasks_find_multiple_criteria_are_anded() -> None:
    """Find should keep tasks that satisfy all provided selectors."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(
        app,
        [
            "tasks",
            "find",
            "--query",
            '.todo == "DONE"',
            "--search-text",
            "Feature implementation details",
            fixture_path,
        ],
    )

    assert result.exit_code == 0
    assert "Implement feature A" in result.output
    assert "Fix bug in parser" not in result.output


def test_tasks_find_include_context_includes_ancestors_without_duplicates(tmp_path: Path) -> None:
    """Context expansion should include parent chain once when matches overlap."""
    runner = CliRunner()
    fixture_path = tmp_path / "context.org"
    fixture_path.write_text(
        "* TODO Parent\n** TODO Child one\nmatch one\n** TODO Child two\nmatch two\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tasks",
            "find",
            "--search-pattern",
            "match",
            "--include-context",
            "1",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    assert result.output.count("* TODO Parent") == 1
    assert "** TODO Child one" in result.output
    assert "** TODO Child two" in result.output


def test_tasks_find_json_output_supported() -> None:
    """Find should support --out json and emit valid JSON."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(
        app,
        ["tasks", "find", "--query-title", "Refactor codebase", "--out", "json", fixture_path],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    assert payload.get("todo") == "TODO"
    assert "Refactor codebase" in result.output


def test_tasks_find_invalid_regex_errors() -> None:
    """Find should fail with a clear error for invalid regex patterns."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(app, ["tasks", "find", "--search-pattern", "(", fixture_path])
    output = _clean_output(result.output)

    assert result.exit_code != 0
    assert "Invalid regex for --search-pattern" in output


def test_tasks_find_negative_include_context_errors() -> None:
    """Find should reject negative --include-context values."""
    runner = CliRunner()
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = runner.invoke(app, ["tasks", "find", "--include-context", "-1", fixture_path])
    output = _clean_output(result.output)

    assert result.exit_code != 0
    assert "--include-context must be non-negative" in output
