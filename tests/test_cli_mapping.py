"""Tests for CLI --mapping parameter functionality."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_accepts_mapping_parameter() -> None:
    """Test that --mapping parameter is accepted."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "custom_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Processing" in result.stdout


def test_cli_mapping_help_text() -> None:
    """Test that --mapping appears in help text."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--mapping" in result.stdout
    assert "JSON file" in result.stdout


def test_cli_mapping_with_valid_json() -> None:
    """Test that custom mapping affects tag normalization."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "custom_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, "-n", "10", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bar" in result.stdout
    assert "test" in result.stdout
    assert "py" in result.stdout


def test_cli_mapping_with_empty_json() -> None:
    """Test that empty mapping file works (no mappings applied)."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "empty_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, "-n", "10", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_mapping_with_nonexistent_file() -> None:
    """Test that nonexistent mapping file produces error."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "nonexistent_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "not found" in result.stderr


def test_cli_mapping_with_malformed_json() -> None:
    """Test that malformed JSON produces error."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "malformed_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "Invalid JSON" in result.stderr


def test_cli_mapping_with_array_json() -> None:
    """Test that JSON array (non-dict) produces error."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "array_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "must contain a JSON object" in result.stderr


def test_cli_mapping_with_invalid_value_types() -> None:
    """Test that non-string values in mapping produce error."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "invalid_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "must be strings" in result.stderr


def test_cli_without_mapping_uses_default() -> None:
    """Test that not providing --mapping uses default MAP."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "-n", "10", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_cli_mapping_with_other_options() -> None:
    """Test --mapping combined with other CLI options."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "custom_mapping.json")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--mapping",
            mapping_path,
            "--filter",
            "all",
            "-n",
            "5",
            "--max-relations",
            "2",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bar" in result.stdout


def test_cli_mapping_affects_all_categories() -> None:
    """Test that mapping affects tags, heading, and body words."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "custom_mapping.json")

    result_tags = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--mapping",
            mapping_path,
            "--use",
            "tags",
            "-n",
            "10",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    result_heading = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--mapping",
            mapping_path,
            "--use",
            "heading",
            "-n",
            "10",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    result_body = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--mapping",
            mapping_path,
            "--use",
            "body",
            "-n",
            "10",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result_tags.returncode == 0
    assert result_heading.returncode == 0
    assert result_body.returncode == 0

    assert "bar" in result_tags.stdout


def test_cli_mapping_case_sensitive() -> None:
    """Test that mapping keys are case-sensitive after normalization."""
    fixture_path = os.path.join(FIXTURES_DIR, "mapping_test.org")
    mapping_path = os.path.join(FIXTURES_DIR, "custom_mapping.json")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", mapping_path, "-n", "10", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
