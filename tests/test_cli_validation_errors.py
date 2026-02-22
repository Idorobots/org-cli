"""Tests for CLI validation and parsing error handling."""

import os
import subprocess
import sys

import pytest


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_validate_and_parse_keys_empty() -> None:
    """Test that empty keys string causes sys.exit()."""
    from org.cli_common import validate_and_parse_keys

    with pytest.raises(SystemExit) as exc_info:
        validate_and_parse_keys("", "--test-keys")

    assert exc_info.value.code == 1


def test_validate_and_parse_keys_whitespace_only() -> None:
    """Test that whitespace-only keys string causes sys.exit()."""
    from org.cli_common import validate_and_parse_keys

    with pytest.raises(SystemExit) as exc_info:
        validate_and_parse_keys("   ", "--test-keys")

    assert exc_info.value.code == 1


def test_validate_and_parse_keys_empty_after_split() -> None:
    """Test that keys string with only commas causes sys.exit()."""
    from org.cli_common import validate_and_parse_keys

    with pytest.raises(SystemExit) as exc_info:
        validate_and_parse_keys(",,,", "--test-keys")

    assert exc_info.value.code == 1


def test_validate_and_parse_keys_pipe_character() -> None:
    """Test that keys containing pipe character cause sys.exit()."""
    from org.cli_common import validate_and_parse_keys

    with pytest.raises(SystemExit) as exc_info:
        validate_and_parse_keys("TODO,IN|PROGRESS,DONE", "--test-keys")

    assert exc_info.value.code == 1


def test_validate_and_parse_keys_pipe_in_first_key() -> None:
    """Test that pipe in first key causes sys.exit()."""
    from org.cli_common import validate_and_parse_keys

    with pytest.raises(SystemExit) as exc_info:
        validate_and_parse_keys("TODO|WAITING,DONE", "--test-keys")

    assert exc_info.value.code == 1


def test_validate_and_parse_keys_valid() -> None:
    """Test that valid keys are parsed correctly."""
    from org.cli_common import validate_and_parse_keys

    result = validate_and_parse_keys("TODO,WAITING,IN-PROGRESS", "--test-keys")
    assert result == ["TODO", "WAITING", "IN-PROGRESS"]


def test_validate_and_parse_keys_with_spaces() -> None:
    """Test that keys with spaces are stripped."""
    from org.cli_common import validate_and_parse_keys

    result = validate_and_parse_keys("TODO , WAITING , DONE", "--test-keys")
    assert result == ["TODO", "WAITING", "DONE"]


def test_parse_date_argument_empty_string() -> None:
    """Test that empty date string causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("", "--test-date")

    assert exc_info.value.code == 1


def test_parse_date_argument_whitespace_only() -> None:
    """Test that whitespace-only date string causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("   ", "--test-date")

    assert exc_info.value.code == 1


def test_parse_date_argument_invalid_format_numbers_only() -> None:
    """Test that YYYYMMDD format is actually accepted by fromisoformat()."""
    from datetime import datetime

    from org.cli_common import parse_date_argument

    result = parse_date_argument("20250115", "--test-date")
    assert result == datetime(2025, 1, 15, 0, 0, 0)


def test_parse_date_argument_invalid_format_slashes() -> None:
    """Test that date with slashes causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("2025/01/15", "--test-date")

    assert exc_info.value.code == 1


def test_parse_date_argument_invalid_format_dots() -> None:
    """Test that date with dots causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("2025.01.15", "--test-date")

    assert exc_info.value.code == 1


def test_parse_date_argument_invalid_format_text() -> None:
    """Test that text date causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("January 15, 2025", "--test-date")

    assert exc_info.value.code == 1


def test_parse_date_argument_invalid_month() -> None:
    """Test that invalid month causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("2025-13-15", "--test-date")

    assert exc_info.value.code == 1


def test_parse_date_argument_invalid_day() -> None:
    """Test that invalid day causes sys.exit()."""
    from org.cli_common import parse_date_argument

    with pytest.raises(SystemExit) as exc_info:
        parse_date_argument("2025-01-32", "--test-date")

    assert exc_info.value.code == 1


def test_parse_property_filter_no_equals() -> None:
    """Test that property filter without '=' causes sys.exit()."""
    from org.cli_common import parse_property_filter

    with pytest.raises(SystemExit) as exc_info:
        parse_property_filter("property_name")

    assert exc_info.value.code == 1


def test_parse_property_filter_valid() -> None:
    """Test that valid property filter is parsed correctly."""
    from org.cli_common import parse_property_filter

    result = parse_property_filter("name=value")
    assert result == ("name", "value")


def test_parse_property_filter_with_equals_in_value() -> None:
    """Test property filter with '=' in value is parsed correctly."""
    from org.cli_common import parse_property_filter

    result = parse_property_filter("name=value=with=equals")
    assert result == ("name", "value=with=equals")


def test_parse_property_filter_empty_value() -> None:
    """Test property filter with empty value."""
    from org.cli_common import parse_property_filter

    result = parse_property_filter("name=")
    assert result == ("name", "")


def test_main_max_relations_zero() -> None:
    """Test that --max-relations 0 is now accepted."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-relations",
            "0",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Top relations:" not in result.stdout


def test_main_max_relations_negative() -> None:
    """Test that --max-relations with negative value causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-relations",
            "-1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --max-relations must be non-negative" in result.stderr


def test_main_min_group_size_negative() -> None:
    """Test that --min-group-size with negative value causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--min-group-size",
            "-1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --min-group-size must be non-negative" in result.stderr


def test_main_min_group_size_negative_large() -> None:
    """Test that --min-group-size with large negative value causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--min-group-size",
            "-100",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --min-group-size must be non-negative" in result.stderr


def test_main_todo_keys_empty() -> None:
    """Test that empty --todo-keys causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--todo-keys",
            "",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --todo-keys cannot be empty" in result.stderr


def test_main_done_keys_empty() -> None:
    """Test that empty --done-keys causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--done-keys",
            "",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --done-keys cannot be empty" in result.stderr


def test_main_todo_keys_with_pipe() -> None:
    """Test that --todo-keys with pipe character causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--todo-keys",
            "TODO|WAITING",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --todo-keys cannot contain pipe character" in result.stderr


def test_main_done_keys_with_pipe() -> None:
    """Test that --done-keys with pipe character causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--done-keys",
            "DONE|CANCELLED",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --done-keys cannot contain pipe character" in result.stderr


def test_main_filter_date_from_invalid() -> None:
    """Test that --filter-date-from with invalid format causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--filter-date-from",
            "2025/01/15",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --filter-date-from must be in one of these formats" in result.stderr


def test_main_filter_date_until_invalid() -> None:
    """Test that --filter-date-until with invalid format causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--filter-date-until",
            "invalid-date",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --filter-date-until must be in one of these formats" in result.stderr


def test_main_filter_property_no_equals() -> None:
    """Test that --filter-property without '=' causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--filter-property",
            "invalid_format",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --filter-property must be in KEY=VALUE format" in result.stderr


def test_main_max_groups_negative() -> None:
    """Test that --max-groups with negative value causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-groups",
            "-1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --max-groups must be non-negative" in result.stderr


def test_main_max_groups_negative_large() -> None:
    """Test that --max-groups with large negative value causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "org",
            "stats",
            "summary",
            "--no-color",
            "--max-groups",
            "-100",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: --max-groups must be non-negative" in result.stderr
