"""Tests for the stats groups CLI command."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_stats_groups_show_order_and_dedup() -> None:
    """Test that --group preserves order and deduplicates within groups."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "groups",
            "--no-color",
            "--group",
            "python,testing,python",
            "--group",
            "java,testing",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    lines = result.stdout.split("\n")
    python_idx = lines.index("python, testing")
    java_idx = lines.index("java, testing")
    assert python_idx < java_idx
    assert "python, python" not in result.stdout


def test_stats_groups_max_results_limits() -> None:
    """Test that -n limits the number of groups displayed."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "groups",
            "--no-color",
            "-n",
            "1",
            "--group",
            "python,testing",
            "--group",
            "java,testing",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "python, testing" in result.stdout
    assert "java, testing" not in result.stdout


def test_stats_groups_no_results() -> None:
    """Test that no results message is shown after filtering."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "groups",
            "--no-color",
            "--filter-tag",
            "doesnotexist",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout


def test_stats_groups_use_heading_with_group() -> None:
    """Test that --use heading works with --group."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "groups",
            "--no-color",
            "--use",
            "heading",
            "--group",
            "task,python",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "task, python" in result.stdout


def test_stats_groups_default_groups() -> None:
    """Test that default grouping shows output without indent."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "groups",
            "--no-color",
            "-n",
            "1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" not in result.stdout

    lines = [line for line in result.stdout.split("\n") if ", " in line and line.strip() == line]
    assert len(lines) > 0
