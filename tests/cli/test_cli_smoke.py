"""Subprocess smoke tests for the CLI entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def test_cli_summary_smoke() -> None:
    """Ensure summary command runs via python -m org."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "stats", "summary", "--no-color", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Total tasks:" in result.stdout


def test_cli_summary_multiple_files_smoke() -> None:
    """Ensure multiple files are processed via CLI."""
    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--no-color",
            fixture1,
            fixture2,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.count("Processing") == 2


def test_cli_stats_tasks_smoke() -> None:
    """Ensure stats tasks runs via CLI without tag sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "stats", "tasks", "--no-color", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Task states:" in result.stdout
    assert "TAGS" not in result.stdout
