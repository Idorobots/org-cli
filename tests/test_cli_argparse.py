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
    assert "--exclude-tags" in result.stdout
    assert "--exclude-heading" in result.stdout
    assert "--exclude-body" in result.stdout
    assert "--tasks" in result.stdout


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


def test_argparse_exclude_tags():
    """Test --exclude-tags with custom file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    stopwords_path = os.path.join(FIXTURES_DIR, "stopwords_tags.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude-tags", stopwords_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Total tasks:" in result.stdout


def test_argparse_exclude_heading():
    """Test --exclude-heading with custom file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    stopwords_path = os.path.join(FIXTURES_DIR, "stopwords_heading.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude-heading", stopwords_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_exclude_body():
    """Test --exclude-body with custom file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    stopwords_path = os.path.join(FIXTURES_DIR, "stopwords_body.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude-body", stopwords_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_all_options():
    """Test using all options together."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    tags_path = os.path.join(FIXTURES_DIR, "stopwords_tags.txt")
    heading_path = os.path.join(FIXTURES_DIR, "stopwords_heading.txt")
    body_path = os.path.join(FIXTURES_DIR, "stopwords_body.txt")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--max-results",
            "20",
            "--exclude-tags",
            tags_path,
            "--exclude-heading",
            heading_path,
            "--exclude-body",
            body_path,
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


def test_argparse_missing_stopwords_file():
    """Test non-existent stopwords file."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nonexistent_file = os.path.join(FIXTURES_DIR, "does_not_exist.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude-tags", nonexistent_file, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "not found" in result.stderr


def test_argparse_empty_stopwords_file():
    """Test empty stopwords file."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    empty_file = os.path.join(FIXTURES_DIR, "stopwords_empty.txt")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--exclude-tags", empty_file, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # Empty stopwords file means no filtering (returns empty set, so defaults are used)
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

    # With argparse and no files, it should still work (empty list)
    assert result.returncode == 0


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


def test_load_stopwords_function():
    """Test load_stopwords helper function directly."""
    from orgstats.cli import load_stopwords

    # Test with None
    result = load_stopwords(None)
    assert result == set()

    # Test with actual file
    stopwords_path = os.path.join(FIXTURES_DIR, "stopwords_tags.txt")
    result = load_stopwords(stopwords_path)
    assert "python" in result
    assert "testing" in result
    assert "debugging" in result

    # Test with empty file
    empty_path = os.path.join(FIXTURES_DIR, "stopwords_empty.txt")
    result = load_stopwords(empty_path)
    assert result == set()


def test_argparse_tasks_default():
    """Test default --tasks behavior (should be total)."""
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


def test_argparse_tasks_simple():
    """Test --tasks simple flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "simple", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout
    assert "Frequency(" not in result.stdout


def test_argparse_tasks_regular():
    """Test --tasks regular flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "regular", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_tasks_hard():
    """Test --tasks hard flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "hard", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_tasks_total():
    """Test explicit --tasks total flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "total", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_tasks_invalid():
    """Test invalid --tasks value."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "invalid", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_argparse_tasks_with_max_results():
    """Test combining --tasks with -n flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--tasks", "hard", "-n", "3", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_argparse_tasks_in_help():
    """Test that --tasks appears in help output."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--tasks" in result.stdout
    assert "simple" in result.stdout
    assert "regular" in result.stdout
    assert "hard" in result.stdout
    assert "total" in result.stdout
