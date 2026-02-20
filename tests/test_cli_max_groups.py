"""Tests for --max-groups CLI option."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_max_groups_default_is_5() -> None:
    """Test that default max_groups is 5."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--max-groups" in result.stdout
    assert "default: 5" in result.stdout


def test_max_groups_limits_groups_section() -> None:
    """Test that --max-groups limits the number of groups displayed."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result_default = subprocess.run(
        [sys.executable, "-m", "orgstats", "--min-group-size", "2", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    result_limited = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--min-group-size",
            "2",
            "--max-groups",
            "1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result_default.returncode == 0
    assert result_limited.returncode == 0
    assert "Tag groups:" in result_default.stdout
    assert "Tag groups:" in result_limited.stdout

    groups_default = result_default.stdout[result_default.stdout.index("Tag groups:") :]
    groups_limited = result_limited.stdout[result_limited.stdout.index("Tag groups:") :]

    assert len(groups_limited) < len(groups_default)


def test_max_groups_zero_omits_section() -> None:
    """Test that --max-groups 0 omits the Tag groups section entirely."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-groups", "0", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" not in result.stdout


def test_max_groups_negative_fails() -> None:
    """Test that negative --max-groups value fails validation."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-groups", "-1", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --max-groups must be non-negative" in result.stderr


def test_max_groups_with_fewer_groups() -> None:
    """Test that --max-groups handles cases with fewer groups than limit."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-groups", "100", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" in result.stdout


def test_max_groups_with_min_group_size() -> None:
    """Test that --max-groups works with --min-group-size filtering."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--min-group-size",
            "2",
            "--max-groups",
            "2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" in result.stdout


def test_max_groups_one() -> None:
    """Test that --max-groups 1 shows only one group."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--min-group-size",
            "2",
            "--max-groups",
            "1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" in result.stdout


def test_max_groups_shows_section_with_no_results() -> None:
    """Test that --max-groups > 0 shows section heading even with no groups."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--min-group-size",
            "100",
            "--max-groups",
            "5",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" in result.stdout


def test_min_group_size_default_is_2() -> None:
    """Test that default min_group_size is 2."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--min-group-size" in result.stdout
    assert "default: 2" in result.stdout
