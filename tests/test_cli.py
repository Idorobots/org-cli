"""Tests for the CLI interface."""

import os
import subprocess
import sys
from pathlib import Path


# Path to project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_runs_successfully() -> None:
    """Test that the CLI runs without errors."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
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

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout
    assert "Task states:" in result.stdout


def test_cli_with_multiple_files() -> None:
    """Test CLI with multiple input files."""
    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
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
    assert "Processing" in result.stdout
    # Should process both files
    assert result.stdout.count("Processing") == 2


def test_cli_outputs_statistics() -> None:
    """Test that CLI outputs expected statistics."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
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

    assert result.returncode == 0
    assert "Total tasks:" in result.stdout
    assert "Task states:" in result.stdout
    assert "TAGS" in result.stdout


def test_cli_stats_tasks_outputs_summary_only() -> None:
    """Test stats tasks output excludes tag/group/task sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tasks",
            "--no-color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Total tasks:" in result.stdout
    assert "Task states:" in result.stdout
    assert "Task categories:" in result.stdout
    assert "Task occurrence by day of week:" in result.stdout
    assert "TASKS" not in result.stdout
    assert "TAGS" not in result.stdout
    assert "GROUPS" not in result.stdout


def test_cli_stats_tasks_no_results() -> None:
    """Test stats tasks output for empty filter results."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "tasks",
            "--no-color",
            "--filter-tag",
            "nomatchtag$",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout


def test_cli_with_archive_small() -> None:
    """Test CLI with the real ARCHIVE_small file."""
    archive_path = os.path.join(PROJECT_ROOT, "examples", "ARCHIVE_small")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            archive_path,
        ],
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

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_handles_24_00_time() -> None:
    """Test that CLI handles 24:00 time format correctly."""
    fixture_path = os.path.join(FIXTURES_DIR, "edge_cases.org")

    result = subprocess.run(
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

    # Should not crash, should complete successfully
    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_no_arguments_no_org_files(tmp_path: Path) -> None:
    """Test CLI behavior with no arguments and no org files."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "stats", "summary", "--no-color"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "No .org files found" in result.stderr


def test_cli_no_arguments_with_org_files(tmp_path: Path) -> None:
    """Test CLI behavior with no arguments when org files exist."""
    (tmp_path / "sample.org").write_text("* TODO Task\n", encoding="utf-8")
    (tmp_path / "another.org").write_text("* DONE Task\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "org", "stats", "summary", "--no-color"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.count("Processing") == 2


def test_cli_directory_argument(tmp_path: Path) -> None:
    """Test CLI behavior with a directory argument."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.org").write_text("* TODO Task\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            str(data_dir),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.count("Processing") == 1


def test_cli_directory_argument_no_org_files(tmp_path: Path) -> None:
    """Test CLI behavior with a directory that has no org files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.txt").write_text("not org", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            str(data_dir),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "No .org files found" in result.stderr


def test_cli_mixed_file_and_directory(tmp_path: Path) -> None:
    """Test CLI behavior with mixed file and directory arguments."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.org").write_text("* TODO Task\n", encoding="utf-8")
    file_path = tmp_path / "direct.org"
    file_path.write_text("* DONE Task\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            str(file_path),
            str(data_dir),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.count("Processing") == 2


def test_cli_tag_filtering() -> None:
    """Test that CLI output shows filtered tags."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
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

    assert result.returncode == 0
    # Output should contain tag with count in parentheses
    assert "(" in result.stdout and ")" in result.stdout
    # Should show integer counts, not Frequency objects
    assert "Frequency(" not in result.stdout


def test_cli_filter_output_format() -> None:
    """Test that output format is integer tuples, not Frequency objects."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
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


def test_cli_outputs_time_ranges() -> None:
    """Test that CLI outputs time range sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
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

    assert result.returncode == 0
    # Time ranges are now shown as charts
    assert "┊" in result.stdout or "(" in result.stdout


def test_cli_time_ranges_format() -> None:
    """Test that time range output contains expected format."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
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

    assert result.returncode == 0
    # Time range data is now shown in charts
    assert "┊" in result.stdout or "(" in result.stdout


def test_cli_default_max_results_is_10() -> None:
    """Test that default max_results is 10."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "stats", "summary", "--no-color", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "default: 10" in result.stdout


def test_cli_displays_top_tasks() -> None:
    """Test that CLI displays TASKS section."""
    fixture_path = os.path.join(FIXTURES_DIR, "repeated_tasks.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            fixture_path,
            "-n",
            "3",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "TASKS" in result.stdout
    assert "TAGS" in result.stdout
    # Top tasks should appear before Top tags
    top_tasks_pos = result.stdout.index("TASKS")
    top_tags_pos = result.stdout.index("TAGS")
    assert top_tasks_pos < top_tags_pos


def test_cli_with_tags_as_category() -> None:
    """Test --with-tags-as-category flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "tags_category_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--with-tags-as-category",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bug" in result.stdout or "work" in result.stdout or "urgent" in result.stdout


def test_cli_with_both_preprocessors() -> None:
    """Test combining --with-gamify-category and --with-tags-as-category."""
    fixture_path = os.path.join(FIXTURES_DIR, "tags_category_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--with-gamify-category",
            "--with-tags-as-category",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "urgent" in result.stdout or "work" in result.stdout
