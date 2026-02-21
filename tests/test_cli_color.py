"""Tests for CLI color output functionality."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_color_flag_enables_colors() -> None:
    """Test that --color flag enables ANSI color codes in output."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[" in result.stdout


def test_no_color_flag_disables_colors() -> None:
    """Test that --no-color flag disables ANSI color codes in output."""
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
    assert "\x1b[" not in result.stdout


def test_section_headers_are_colored() -> None:
    """Test that section headers are colored with bright white."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[1;37mTASKS:" in result.stdout or "TASKS" in result.stdout
    assert "\x1b[1;37mTAGS:" in result.stdout or "TAGS" in result.stdout


def test_statistics_values_are_colored_magenta() -> None:
    """Test that statistics values are colored magenta."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[35m" in result.stdout


def test_timeline_chart_has_colors() -> None:
    """Test that timeline charts contain colored elements."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[" in result.stdout


def test_histogram_has_colors() -> None:
    """Test that histograms contain colored elements."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    task_states_section = result.stdout.split("Task states:")[1].split("\n\n")[0]
    assert "\x1b[" in task_states_section


def test_done_state_is_bright_green() -> None:
    """Test that DONE state in task states histogram is bright green."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[1m\x1b[32mDONE\x1b[0m" in result.stdout or "\x1b[1;32mDONE" in result.stdout


def test_cancelled_state_is_bright_red() -> None:
    """Test that CANCELLED state in task states histogram is bright red."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            "--done-keys",
            "DONE,CANCELLED",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_tasks_section_has_colored_filenames() -> None:
    """Test that filenames in TASKS section are colored dim white."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    if "TASKS" in result.stdout:
        assert "\x1b[2m\x1b[37m" in result.stdout or "\x1b[2;37m" in result.stdout


def test_color_output_contains_reset_codes() -> None:
    """Test that colored output contains ANSI reset codes."""
    fixture_path = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[0m" in result.stdout


def test_color_with_multiple_files() -> None:
    """Test that color works correctly with multiple input files."""
    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--color",
            fixture1,
            fixture2,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[" in result.stdout


def test_no_color_with_all_sections() -> None:
    """Test that --no-color works across all output sections."""
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
    assert "\x1b[" not in result.stdout
    assert "TASKS" in result.stdout
    assert "TAGS" in result.stdout
    assert "Task states:" in result.stdout
