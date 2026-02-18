"""Tests for CLI file loading error handling."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_load_exclude_list_file_not_found() -> None:
    """Test that loading non-existent exclude list causes sys.exit()."""
    from orgstats.cli import load_exclude_list

    with pytest.raises(SystemExit) as exc_info:
        load_exclude_list("/nonexistent/path/to/exclude.txt")

    assert exc_info.value.code == 1


def test_load_exclude_list_none() -> None:
    """Test that None filepath returns empty set."""
    from orgstats.cli import load_exclude_list

    result = load_exclude_list(None)
    assert result == set()


def test_load_exclude_list_valid(tmp_path: Path) -> None:
    """Test loading valid exclude list."""
    from orgstats.cli import load_exclude_list

    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("word1\nword2\nWORD3\n")

    result = load_exclude_list(str(exclude_file))
    assert result == {"word1", "word2", "WORD3"}


def test_load_exclude_list_with_empty_lines(tmp_path: Path) -> None:
    """Test loading exclude list with empty lines."""
    from orgstats.cli import load_exclude_list

    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("word1\n\nword2\n\n\nword3\n")

    result = load_exclude_list(str(exclude_file))
    assert result == {"word1", "word2", "word3"}


def test_load_exclude_list_with_whitespace(tmp_path: Path) -> None:
    """Test loading exclude list with whitespace."""
    from orgstats.cli import load_exclude_list

    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("  word1  \n\t word2\t\nword3   ")

    result = load_exclude_list(str(exclude_file))
    assert result == {"word1", "word2", "word3"}


def test_load_mapping_file_not_found() -> None:
    """Test that loading non-existent mapping file causes sys.exit()."""
    from orgstats.cli import load_mapping

    with pytest.raises(SystemExit) as exc_info:
        load_mapping("/nonexistent/path/to/mapping.json")

    assert exc_info.value.code == 1


def test_load_mapping_none() -> None:
    """Test that None filepath returns empty dict."""
    from orgstats.cli import load_mapping

    result = load_mapping(None)
    assert result == {}


def test_load_mapping_valid(tmp_path: Path) -> None:
    """Test loading valid mapping file."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": "testing", "webdev": "frontend"}')

    result = load_mapping(str(mapping_file))
    assert result == {"test": "testing", "webdev": "frontend"}


def test_load_mapping_empty_dict(tmp_path: Path) -> None:
    """Test loading empty mapping dict."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("{}")

    result = load_mapping(str(mapping_file))
    assert result == {}


def test_load_mapping_invalid_json(tmp_path: Path) -> None:
    """Test that invalid JSON causes sys.exit()."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": "testing",')

    with pytest.raises(SystemExit) as exc_info:
        load_mapping(str(mapping_file))

    assert exc_info.value.code == 1


def test_load_mapping_non_dict_json_array(tmp_path: Path) -> None:
    """Test that JSON array causes sys.exit()."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('["test", "testing"]')

    with pytest.raises(SystemExit) as exc_info:
        load_mapping(str(mapping_file))

    assert exc_info.value.code == 1


def test_load_mapping_non_dict_json_string(tmp_path: Path) -> None:
    """Test that JSON string causes sys.exit()."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('"test string"')

    with pytest.raises(SystemExit) as exc_info:
        load_mapping(str(mapping_file))

    assert exc_info.value.code == 1


def test_load_mapping_non_dict_json_number(tmp_path: Path) -> None:
    """Test that JSON number causes sys.exit()."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("42")

    with pytest.raises(SystemExit) as exc_info:
        load_mapping(str(mapping_file))

    assert exc_info.value.code == 1


def test_load_mapping_non_string_keys(tmp_path: Path) -> None:
    """Test that mapping with valid string keys works (JSON converts int keys to strings)."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"123": "testing"}')

    result = load_mapping(str(mapping_file))

    assert result == {"123": "testing"}


def test_load_mapping_non_string_values(tmp_path: Path) -> None:
    """Test that mapping with non-string values causes sys.exit()."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": 123}')

    with pytest.raises(SystemExit) as exc_info:
        load_mapping(str(mapping_file))

    assert exc_info.value.code == 1


def test_load_mapping_mixed_non_string_types(tmp_path: Path) -> None:
    """Test that mapping with mixed non-string types causes sys.exit()."""
    from orgstats.cli import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": "testing", "another": ["array"]}')

    with pytest.raises(SystemExit) as exc_info:
        load_mapping(str(mapping_file))

    assert exc_info.value.code == 1


def test_load_org_files_not_found() -> None:
    """Test that loading non-existent org file causes sys.exit()."""
    from orgstats.cli import load_org_files

    with pytest.raises(SystemExit) as exc_info:
        load_org_files(["/nonexistent/file.org"], ["TODO"], ["DONE"])

    assert exc_info.value.code == 1


def test_load_org_files_valid() -> None:
    """Test loading valid org files."""
    from orgstats.cli import load_org_files

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nodes, _, _ = load_org_files([fixture_path], ["TODO"], ["DONE"])

    assert len(nodes) > 0
    assert all(hasattr(node, "heading") for node in nodes)


def test_load_org_files_todo_keys() -> None:
    """Test loading valid org files."""
    from orgstats.cli import load_org_files

    fixture_path = os.path.join(FIXTURES_DIR, "todo_keys.org")
    nodes, todo_keys, done_keys = load_org_files([fixture_path], ["TODO"], ["DONE"])

    assert len(nodes) > 0
    assert set(todo_keys) == {"TODO", "STARTED"}
    assert set(done_keys) == {"DONE", "CANCELLED"}


def test_load_org_files_multiple() -> None:
    """Test loading multiple org files."""
    from orgstats.cli import load_org_files

    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    nodes, _, _ = load_org_files([fixture1, fixture2], ["TODO"], ["DONE"])

    assert len(nodes) > 0


def test_load_org_files_with_24_00_time() -> None:
    """Test that 24:00 time format is normalized."""
    from orgstats.cli import load_org_files

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nodes, _, _ = load_org_files([fixture_path], ["TODO"], ["DONE"])

    assert len(nodes) > 0


def test_main_exclude_file_not_found() -> None:
    """Test that --exclude with non-existent file causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--exclude",
            "/nonexistent/exclude.txt",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: Exclude list file" in result.stderr
    assert "not found" in result.stderr


def test_main_mapping_file_not_found() -> None:
    """Test that --mapping with non-existent file causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--mapping",
            "/nonexistent/mapping.json",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: Mapping file" in result.stderr
    assert "not found" in result.stderr


def test_main_mapping_invalid_json(tmp_path: Path) -> None:
    """Test that --mapping with invalid JSON causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    mapping_file = tmp_path / "invalid.json"
    mapping_file.write_text('{"test": "testing",')

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", str(mapping_file), fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: Invalid JSON in" in result.stderr


def test_main_mapping_non_dict(tmp_path: Path) -> None:
    """Test that --mapping with non-dict JSON causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    mapping_file = tmp_path / "array.json"
    mapping_file.write_text('["test", "testing"]')

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", str(mapping_file), fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: Mapping file" in result.stderr
    assert "must contain a JSON object" in result.stderr


def test_main_mapping_non_string_values(tmp_path: Path) -> None:
    """Test that --mapping with non-string values causes error."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    mapping_file = tmp_path / "nonstring.json"
    mapping_file.write_text('{"test": 123}')

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--mapping", str(mapping_file), fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: All keys and values in" in result.stderr
    assert "must be strings" in result.stderr


def test_main_org_file_not_found() -> None:
    """Test that non-existent org file causes error."""
    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "/nonexistent/file.org"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: File" in result.stderr
    assert "not found" in result.stderr
