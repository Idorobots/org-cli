"""Tests for argparse functionality in CLI."""

import os
import subprocess
import sys


# Path to project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_argparse_help():
    """Test --help output."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "orgstats" in result.stdout
    assert "--max-results" in result.stdout
    assert "--exclude" in result.stdout
    assert "--filter" in result.stdout


def test_argparse_max_results_long():
    """Test --max-results flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-results", "5", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout


def test_argparse_max_results_short():
    """Test -n short flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "-n", "10", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_exclude():
    """Test --exclude with custom file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    exclude_list_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude", exclude_list_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout


def test_argparse_all_options():
    """Test using all options together."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    exclude_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--max-results",
            "20",
            "--exclude",
            exclude_path,
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_invalid_max_results():
    """Test invalid max-results value."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--max-results", "not-a-number", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # argparse will exit with error
    assert result.returncode != 0
    assert "invalid int value" in result.stderr or "error" in result.stderr.lower()


def test_argparse_missing_exclude_list_file():
    """Test non-existent exclude_list file."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nonexistent_file = os.path.join(FIXTURES_DIR, "does_not_exist.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude", nonexistent_file, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "not found" in result.stderr


def test_argparse_empty_exclude_list_file():
    """Test empty exclude_list file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    empty_file = os.path.join(FIXTURES_DIR, "exclude_list_empty.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude", empty_file, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # Empty exclude file means no filtering (returns empty set, so defaults are used)
    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_backward_compatibility():
    """Test that old-style invocation still works."""
    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    # Old style: just filenames as positional arguments
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture1, fixture2],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert result.stdout.count("Processing") == 2
    assert "Total tasks:" in result.stdout


def test_argparse_no_files_provided():
    """Test behavior when no files are provided."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # It should complain than at least one FILE is required.
    assert result.returncode == 2
    assert "the following arguments are required:" in result.stderr


def test_argparse_options_before_files():
    """Test that options can come before filenames."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "-n", "50", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_options_after_files():
    """Test that options can come after filenames."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path, "-n", "50"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_load_exclude_list_function():
    """Test load_exclude_list helper function directly."""
    from orgstats.cli import load_exclude_list

    # Test with None
    result = load_exclude_list(None)
    assert result == set()

    # Test with actual file
    exclude_list_path = os.path.join(FIXTURES_DIR, "exclude_list_tags.txt")
    result = load_exclude_list(exclude_list_path)
    assert "python" in result
    assert "testing" in result
    assert "debugging" in result

    # Test with empty file
    empty_path = os.path.join(FIXTURES_DIR, "exclude_list_empty.txt")
    result = load_exclude_list(empty_path)
    assert result == set()


def test_argparse_filter_default():
    """Test default --filter behavior (should be all)."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    # Should show integer tuples, not Frequency objects
    assert "Frequency(" not in result.stdout


def test_argparse_filter_simple():
    """Test --filter simple flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "simple", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Frequency(" not in result.stdout


def test_argparse_filter_regular():
    """Test --filter regular flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "regular", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_hard():
    """Test --filter hard flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "hard", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_all():
    """Test explicit --filter all flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "all", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_invalid():
    """Test invalid --filter value."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "invalid", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_argparse_filter_with_max_results():
    """Test combining --filter with -n flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--filter", "hard", "-n", "3", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_filter_in_help():
    """Test that --filter appears in help output."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--filter" in result.stdout
    assert "simple" in result.stdout
    assert "regular" in result.stdout
    assert "hard" in result.stdout
    assert "all" in result.stdout
