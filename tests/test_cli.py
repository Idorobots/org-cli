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
        [sys.executable, "src/cli.py", fixture_path],
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
        [sys.executable, "src/cli.py", fixture1, fixture2],
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
        [sys.executable, "src/cli.py", fixture_path],
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
        [sys.executable, "src/cli.py", archive_path],
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
        [sys.executable, "src/cli.py", fixture_path],
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
        [sys.executable, "src/cli.py", fixture_path],
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
        [sys.executable, "src/cli.py"], cwd=PROJECT_ROOT, capture_output=True, text=True
    )

    # Should complete without error even with no files
    assert result.returncode == 0


def test_cli_tag_filtering():
    """Test that CLI output shows filtered tags."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "src/cli.py", fixture_path],
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
        [sys.executable, "src/cli.py", "--tasks", "simple", fixture_path],
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
        [sys.executable, "src/cli.py", "--tasks", "hard", fixture_path],
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
        [sys.executable, "src/cli.py", "--tasks", "total", fixture_path],
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
            "src/cli.py",
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
