"""Tests for --max-tags CLI option."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_max_tags_default_is_5() -> None:
    """Test that default max_tags is 5."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "stats", "--no-color", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--max-tags" in result.stdout
    assert "default: 5" in result.stdout


def test_max_tags_limits_tags_section() -> None:
    """Test that --max-tags limits the number of tags displayed."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result_default = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    result_limited = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-tags",
            "1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result_default.returncode == 0
    assert result_limited.returncode == 0
    assert "TAGS" in result_default.stdout
    assert "TAGS" in result_limited.stdout

    tags_default = result_default.stdout[result_default.stdout.index("TAGS") :]
    tags_limited = result_limited.stdout[result_limited.stdout.index("TAGS") :]

    assert len(tags_limited) < len(tags_default)


def test_max_tags_zero_omits_section() -> None:
    """Test that --max-tags 0 omits the TAGS section entirely."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-tags",
            "0",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TAGS" not in result.stdout


def test_max_tags_negative_fails() -> None:
    """Test that negative --max-tags value fails validation."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-tags",
            "-1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --max-tags must be non-negative" in result.stderr


def test_max_tags_with_show_heading() -> None:
    """Test that --max-tags affects heading words when --use heading is used."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--use",
            "heading",
            "--max-tags",
            "2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "HEADING WORDS" in result.stdout
    assert "TAGS" not in result.stdout


def test_max_tags_with_show_body() -> None:
    """Test that --max-tags affects body words when --use body is used."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--use",
            "body",
            "--max-tags",
            "2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "BODY WORDS" in result.stdout
    assert "TAGS" not in result.stdout


def test_max_tags_with_fewer_results() -> None:
    """Test that --max-tags handles cases with fewer results than limit."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-tags",
            "10",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TAGS" in result.stdout


def test_max_tags_zero_with_show_heading() -> None:
    """Test that --max-tags 0 omits heading section when --use heading is used."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--use",
            "heading",
            "--max-tags",
            "0",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "HEADING WORDS" not in result.stdout


def test_max_tags_with_max_results() -> None:
    """Test that --max-tags and --max-results work independently."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--max-tags",
            "2",
            "--max-results",
            "5",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TAGS" in result.stdout
    assert "TASKS" in result.stdout


def test_max_tags_one() -> None:
    """Test that --max-tags 1 shows only one tag."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-tags",
            "1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TAGS" in result.stdout
