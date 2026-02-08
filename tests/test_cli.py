"""Tests for the CLI interface."""

import os
import subprocess
import sys


# Path to project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_runs_successfully():
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
    assert "Done tasks:" in result.stdout


def test_cli_with_multiple_files():
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


def test_cli_outputs_statistics():
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
    assert "Done tasks:" in result.stdout
    assert "Top tags:" in result.stdout
    assert "Top words in headline:" in result.stdout
    assert "Top words in body:" in result.stdout


def test_cli_with_archive_small():
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
    assert "Done tasks:" in result.stdout


def test_cli_via_cli_module():
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


def test_cli_handles_24_00_time():
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


def test_cli_no_arguments():
    """Test CLI behavior with no arguments."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats"], cwd=PROJECT_ROOT, capture_output=True, text=True
    )

    # Should report that at least one file is required.
    assert result.returncode == 2


def test_cli_tag_filtering():
    """Test that CLI output shows filtered tags."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Output should contain tag frequencies as tuples
    assert "[(" in result.stdout or "[]" in result.stdout
    # Should show integer tuples, not Frequency objects
    assert "Frequency(" not in result.stdout


def test_cli_tasks_simple_sorting():
    """Test that --tasks simple sorts by simple count."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "simple", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # simpletag has 2 simple tasks, should appear near top
    assert "simpletag" in result.stdout
    # Output should be integer tuples
    assert "Frequency(" not in result.stdout


def test_cli_tasks_hard_sorting():
    """Test that --tasks hard sorts by hard count."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "hard", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # hardtag has 3 hard tasks, should appear near top
    assert "hardtag" in result.stdout


def test_cli_tasks_output_format():
    """Test that output format is integer tuples, not Frequency objects."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "total", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Should have tuples with integers
    assert "[(" in result.stdout
    # Should NOT have Frequency objects
    assert "Frequency(" not in result.stdout
    assert "simple=" not in result.stdout
    assert "regular=" not in result.stdout
    assert "hard=" not in result.stdout


def test_cli_tasks_combined_options():
    """Test --tasks with other CLI options."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")
    stopwords_path = os.path.join(FIXTURES_DIR, "stopwords_tags.txt")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--tasks",
            "regular",
            "-n",
            "5",
            "--exclude-tags",
            stopwords_path,
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_outputs_time_ranges():
    """Test that CLI outputs time range sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag time ranges:" in result.stdout
    assert "Heading word time ranges:" in result.stdout
    assert "Body word time ranges:" in result.stdout


def test_cli_time_ranges_format():
    """Test that time range output contains expected format."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TimeRange(" in result.stdout
    assert "top_day=" in result.stdout


def test_cli_default_max_results_is_10():
    """Test that default max_results is 10."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "default: 10" in result.stdout
