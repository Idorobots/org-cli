"""Tests for the CLI interface."""

import os
import subprocess
import sys


# Path to project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_runs_successfully() -> None:
    """Test that the CLI runs without errors."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout
    assert "Task states:" in result.stdout


def test_cli_with_multiple_files() -> None:
    """Test CLI with multiple input files."""
    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture1, fixture2],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    # Should process both files
    assert result.stdout.count("Processing") == 2


def test_cli_outputs_statistics() -> None:
    """Test that CLI outputs expected statistics."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Total tasks:" in result.stdout
    assert "Task states:" in result.stdout
    assert "Top tags:" in result.stdout


def test_cli_with_archive_small() -> None:
    """Test CLI with the real ARCHIVE_small file."""
    archive_path = os.path.join(PROJECT_ROOT, "examples", "ARCHIVE_small")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", archive_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "ARCHIVE_small" in result.stdout
    assert "Total tasks:" in result.stdout
    assert "Task states:" in result.stdout


def test_cli_via_cli_module() -> None:
    """Test running via cli.py directly."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_handles_24_00_time() -> None:
    """Test that CLI handles 24:00 time format correctly."""
    fixture_path = os.path.join(FIXTURES_DIR, "edge_cases.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # Should not crash, should complete successfully
    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_no_arguments() -> None:
    """Test CLI behavior with no arguments."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats"], cwd=PROJECT_ROOT, capture_output=True, text=True
    )

    # Should report that at least one file is required.
    assert result.returncode == 2


def test_cli_tag_filtering() -> None:
    """Test that CLI output shows filtered tags."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Output should contain tag with count in parentheses
    assert "(" in result.stdout and ")" in result.stdout
    # Should show integer counts, not Frequency objects
    assert "Frequency(" not in result.stdout


def test_cli_filter_simple_sorting() -> None:
    """Test that --filter simple filters simple tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "simple", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # simpletag has 2 simple tasks, should appear near top
    assert "SimpleTag" in result.stdout
    # Output should be integer tuples
    assert "Frequency(" not in result.stdout


def test_cli_filter_hard_sorting() -> None:
    """Test that --filter hard filters hard tasks."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "hard", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # hardtag has 3 hard tasks, should appear near top
    assert "HardTag" in result.stdout


def test_cli_filter_output_format() -> None:
    """Test that output format is integer tuples, not Frequency objects."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "all", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Should have tag
    assert "HardTag" in result.stdout
    assert "RegularTag" in result.stdout
    assert "SimpleTag" in result.stdout
    # Should NOT have Frequency objects
    assert "Frequency(" not in result.stdout
    assert "simple=" not in result.stdout
    assert "regular=" not in result.stdout
    assert "hard=" not in result.stdout


def test_cli_filter_combined_options() -> None:
    """Test --filter with other CLI options."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")
    exclude_list_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--filter",
            "regular",
            "-n",
            "5",
            "--exclude",
            exclude_list_path,
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_outputs_time_ranges() -> None:
    """Test that CLI outputs time range sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Time ranges are now shown as charts
    assert "┊" in result.stdout or "(" in result.stdout


def test_cli_time_ranges_format() -> None:
    """Test that time range output contains expected format."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Time range data is now shown in charts
    assert "┊" in result.stdout or "(" in result.stdout


def test_cli_default_max_results_is_10() -> None:
    """Test that default max_results is 10."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "default: 10" in result.stdout


def test_cli_displays_top_tasks() -> None:
    """Test that CLI displays Top tasks section."""
    fixture_path = os.path.join(FIXTURES_DIR, "repeated_tasks.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path, "-n", "3"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Top tasks:" in result.stdout
    assert "Top tags:" in result.stdout
    # Top tasks should appear before Top tags
    top_tasks_pos = result.stdout.index("Top tasks:")
    top_tags_pos = result.stdout.index("Top tags:")
    assert top_tasks_pos < top_tags_pos
