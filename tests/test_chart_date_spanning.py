"""Tests for chart spanning with date filter arguments."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_chart_spanning_no_filters() -> None:
    """Test chart displays without date filters uses timeline's own dates."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--no-color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout


def test_chart_spanning_with_filter_date_from_only() -> None:
    """Test chart spans from filter-date-from to actual latest date."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--filter-date-from",
            "2024-01-01",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    lines = result.stdout.split("\n")
    date_lines = [line for line in lines if "2024-" in line]
    assert len(date_lines) > 0


def test_chart_spanning_with_filter_date_until_only() -> None:
    """Test chart spans from actual earliest to filter-date-until."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--filter-date-until",
            "2025-12-31",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    lines = result.stdout.split("\n")
    date_lines = [line for line in lines if "2025-" in line]
    assert len(date_lines) > 0


def test_chart_spanning_with_both_date_filters() -> None:
    """Test chart spans from filter-date-from to filter-date-until."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--filter-date-from",
            "2024-01-01",
            "--filter-date-until",
            "2025-12-31",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    lines = result.stdout.split("\n")
    has_2024 = any("2024-" in line for line in lines)
    has_2025 = any("2025-" in line for line in lines)
    assert has_2024 or has_2025


def test_chart_spanning_with_narrow_date_range() -> None:
    """Test chart with narrow date range still works."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--filter-date-from",
            "2025-01-01",
            "--filter-date-until",
            "2025-01-31",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_chart_spanning_filters_out_all_data() -> None:
    """Test chart when date filters exclude all data shows 'No results'."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--filter-date-from",
            "2099-01-01",
            "--filter-date-until",
            "2099-12-31",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout


def test_chart_spanning_with_show_heading() -> None:
    """Test chart spanning works with --use heading."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--use",
            "heading",
            "--filter-date-from",
            "2024-01-01",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "HEADING WORDS" in result.stdout


def test_chart_spanning_with_show_body() -> None:
    """Test chart spanning works with --use body."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--use",
            "body",
            "--filter-date-from",
            "2024-01-01",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "BODY WORDS" in result.stdout


def test_chart_spanning_with_time_component() -> None:
    """Test chart spanning with timestamp including time."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--verbose",
            "stats",
            "summary",
            "--filter-date-from",
            "2024-01-01T00:00:00",
            "--filter-date-until",
            "2025-12-31T23:59:59",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
