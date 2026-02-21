"""CLI tests for regex filter arguments."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_filter_tag_regex_basic() -> None:
    """Test --filter-tag with basic regex pattern."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-tag", "tag.*", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_tag_regex_exact() -> None:
    """Test --filter-tag with exact match using anchors."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-tag", "^tag1$", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_tag_regex_alternation() -> None:
    """Test --filter-tag with alternation (OR)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-tag", "tag1|tag2", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_tag_invalid_regex() -> None:
    """Test --filter-tag with invalid regex pattern."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-tag", "[invalid", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Invalid regex pattern" in result.stderr
    assert "--filter-tag" in result.stderr


def test_cli_filter_heading_basic() -> None:
    """Test --filter-heading with basic regex pattern."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-heading", "Task", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_heading_alternation() -> None:
    """Test --filter-heading with alternation."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-heading",
            "bug|fix",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_heading_word_boundary() -> None:
    """Test --filter-heading with word boundary."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-heading",
            r"\btest\b",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_heading_invalid_regex() -> None:
    """Test --filter-heading with invalid regex pattern."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-heading",
            "(unclosed",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Invalid regex pattern" in result.stderr
    assert "--filter-heading" in result.stderr


def test_cli_filter_body_basic() -> None:
    """Test --filter-body with basic regex pattern."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-body", "content", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_filter_body_multiline_anchor() -> None:
    """Test --filter-body with multiline anchor."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-body", "^TODO:", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_body_alternation() -> None:
    """Test --filter-body with alternation."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--no-color",
            "--filter-body",
            "TODO|FIXME",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_body_invalid_regex() -> None:
    """Test --filter-body with invalid regex pattern."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-body", "*invalid", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Invalid regex pattern" in result.stderr
    assert "--filter-body" in result.stderr


def test_cli_filter_multiple_headings() -> None:
    """Test multiple --filter-heading arguments (AND logic)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-heading",
            "Task",
            "--filter-heading",
            "[0-9]",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_multiple_bodies() -> None:
    """Test multiple --filter-body arguments (AND logic)."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-body",
            "content",
            "--filter-body",
            "test",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_combined_regex_filters() -> None:
    """Test combining tag, heading, and body filters."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-tag",
            "tag1",
            "--filter-heading",
            "Task",
            "--filter-body",
            "content",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_regex_with_other_filters() -> None:
    """Test combining regex filters with other filter types."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "--filter-completed",
            "--filter-tag",
            "tag.*",
            "--filter-heading",
            "Task",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_help_shows_regex_options() -> None:
    """Test that --help displays regex filter options."""
    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--filter-tag" in result.stdout
    assert "--filter-heading" in result.stdout
    assert "--filter-body" in result.stdout
    assert "regex" in result.stdout.lower() or "REGEX" in result.stdout


def test_cli_filter_tag_case_sensitive() -> None:
    """Test --filter-tag is case-sensitive."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-tag", "Tag1", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_heading_case_sensitive() -> None:
    """Test --filter-heading is case-sensitive."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-heading", "task", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_filter_body_case_sensitive() -> None:
    """Test --filter-body is case-sensitive."""
    fixture_path = os.path.join(FIXTURES_DIR, "comprehensive_filter_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "org", "--no-color", "--filter-body", "Content", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
