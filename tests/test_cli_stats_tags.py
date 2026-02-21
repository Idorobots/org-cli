"""Tests for the stats tags CLI command."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def extract_tag_lines(output: str, candidates: set[str]) -> list[str]:
    """Extract lines that match tag candidates exactly."""
    return [line for line in output.split("\n") if line in candidates]


def test_stats_tags_top_results_limit() -> None:
    """Test that -n limits tag output to top results."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tags",
            "--no-color",
            "-n",
            "2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    candidates = {
        "python",
        "testing",
        "debugging",
        "algorithms",
        "datastructures",
        "java",
        "isolated",
    }
    tag_lines = extract_tag_lines(result.stdout, candidates)
    assert tag_lines[:2] == ["python", "testing"]


def test_stats_tags_show_order_and_missing() -> None:
    """Test that --show preserves order and omits missing tags."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tags",
            "--no-color",
            "--show",
            "testing,python,missing,isolated",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    candidates = {
        "python",
        "testing",
        "debugging",
        "algorithms",
        "datastructures",
        "java",
        "isolated",
        "missing",
    }
    tag_lines = extract_tag_lines(result.stdout, candidates)
    assert tag_lines == ["testing", "python", "isolated"]


def test_stats_tags_no_results() -> None:
    """Test that no results message is shown after filtering."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tags",
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


def test_stats_tags_max_relations_zero_omits() -> None:
    """Test that --max-relations 0 omits relation sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tags",
            "--no-color",
            "--max-relations",
            "0",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Top relations:" not in result.stdout


def test_stats_tags_use_heading_with_show() -> None:
    """Test that --use heading works with --show."""
    fixture_path = os.path.join(FIXTURES_DIR, "relations_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tags",
            "--no-color",
            "--use",
            "heading",
            "--show",
            "task",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "task" in result.stdout
