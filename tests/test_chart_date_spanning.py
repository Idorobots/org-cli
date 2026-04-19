"""Tests for chart spanning with date filter arguments."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

import pytest
from typer.testing import CliRunner

from org.cli import app


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class _CliResult(Protocol):
    """Typing protocol for CliRunner invocation results."""

    @property
    def stdout(self) -> str:
        """Captured stdout text."""
        ...

    @property
    def stderr(self) -> str:
        """Captured stderr text."""
        ...

    @property
    def exit_code(self) -> int:
        """Process exit code."""
        ...


def _clean_combined_output(result: _CliResult) -> str:
    """Return stdout+stderr with ANSI escape sequences removed."""
    return ANSI_ESCAPE_RE.sub("", result.stdout + result.stderr)


def _run_stats_all(extra_args: list[str]) -> str:
    """Run org stats all in-process and return cleaned combined output."""
    fixture_path = str((FIXTURES_DIR / "comprehensive_filter_test.org").resolve())
    runner = CliRunner()
    logger = logging.getLogger("org")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    previous_propagate = logger.propagate
    try:
        result = runner.invoke(
            app,
            ["--verbose", "stats", "all", "--no-color", *extra_args, fixture_path],
        )
    finally:
        logger.handlers.clear()
        logger.handlers.extend(previous_handlers)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
    assert result.exit_code == 0
    return _clean_combined_output(result)


@pytest.mark.parametrize(
    ("extra_args", "required_tokens", "any_of_tokens"),
    [
        ([], ["Processing", "Total tasks:"], []),
        (["--filter-date-from", "2024-01-01"], ["Processing"], ["2024-"]),
        (["--filter-date-until", "2025-12-31"], ["Processing"], ["2025-"]),
        (
            ["--filter-date-from", "2024-01-01", "--filter-date-until", "2025-12-31"],
            ["Processing"],
            ["2024-", "2025-"],
        ),
        (
            ["--filter-date-from", "2025-01-01", "--filter-date-until", "2025-01-31"],
            ["Processing"],
            [],
        ),
        (
            ["--filter-date-from", "2099-01-01", "--filter-date-until", "2099-12-31"],
            ["No results"],
            [],
        ),
        (
            ["--use", "heading", "--filter-date-from", "2024-01-01"],
            ["Processing", "HEADING WORDS"],
            [],
        ),
        (["--use", "body", "--filter-date-from", "2024-01-01"], ["Processing", "BODY WORDS"], []),
        (
            [
                "--filter-date-from",
                "2024-01-01T00:00:00",
                "--filter-date-until",
                "2025-12-31T23:59:59",
            ],
            ["Processing"],
            [],
        ),
    ],
)
def test_chart_spanning_cases(
    extra_args: list[str],
    required_tokens: list[str],
    any_of_tokens: list[str],
) -> None:
    """Chart spanning should work for date filters and rendering variants."""
    combined_output = _run_stats_all(extra_args)

    for token in required_tokens:
        assert token in combined_output
    if any_of_tokens:
        assert any(token in combined_output for token in any_of_tokens)
