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
        [sys.executable, "src/main.py", "--help"],
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


def test_argparse_max_results_long():
    """Test --max-results flag."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")

    result = subprocess.run(
        [sys.executable, "src/main.py", "--max-results", "5", fixture_path],
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
        [sys.executable, "src/main.py", "-n", "10", fixture_path],
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
        [sys.executable, "src/main.py", "--exclude-tags", stopwords_path, fixture_path],
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
        [sys.executable, "src/main.py", "--exclude-heading", stopwords_path, fixture_path],
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
        [sys.executable, "src/main.py", "--exclude-body", stopwords_path, fixture_path],
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
            "src/main.py",
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
        [sys.executable, "src/main.py", "--max-results", "not-a-number", fixture_path],
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
        [sys.executable, "src/main.py", "--exclude-tags", nonexistent_file, fixture_path],
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
        [sys.executable, "src/main.py", "--exclude-tags", empty_file, fixture_path],
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
        [sys.executable, "src/main.py", fixture1, fixture2],
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
        [sys.executable, "src/main.py"],
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
        [sys.executable, "src/main.py", "-n", "50", fixture_path],
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
        [sys.executable, "src/main.py", fixture_path, "-n", "50"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_load_stopwords_function():
    """Test load_stopwords helper function directly."""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
    from cli import load_stopwords

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
