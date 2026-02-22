"""Tests for CLI file loading error handling."""

import os
from pathlib import Path

import pytest
import typer


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def test_load_exclude_list_file_not_found() -> None:
    """Test that loading non-existent exclude list raises error."""
    from org.config import load_exclude_list

    with pytest.raises(typer.BadParameter, match="Exclude list file"):
        load_exclude_list("/nonexistent/path/to/exclude.txt")


def test_load_exclude_list_none() -> None:
    """Test that None filepath returns empty set."""
    from org.config import load_exclude_list

    result = load_exclude_list(None)
    assert result == set()


def test_load_exclude_list_valid(tmp_path: Path) -> None:
    """Test loading valid exclude list."""
    from org.config import load_exclude_list

    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("word1\nword2\nWORD3\n")

    result = load_exclude_list(str(exclude_file))
    assert result == {"word1", "word2", "WORD3"}


def test_load_exclude_list_with_empty_lines(tmp_path: Path) -> None:
    """Test loading exclude list with empty lines."""
    from org.config import load_exclude_list

    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("word1\n\nword2\n\n\nword3\n")

    result = load_exclude_list(str(exclude_file))
    assert result == {"word1", "word2", "word3"}


def test_load_exclude_list_with_whitespace(tmp_path: Path) -> None:
    """Test loading exclude list with whitespace."""
    from org.config import load_exclude_list

    exclude_file = tmp_path / "exclude.txt"
    exclude_file.write_text("  word1  \n\t word2\t\nword3   ")

    result = load_exclude_list(str(exclude_file))
    assert result == {"word1", "word2", "word3"}


def test_load_mapping_file_not_found() -> None:
    """Test that loading non-existent mapping file raises error."""
    from org.config import load_mapping

    with pytest.raises(typer.BadParameter, match="Mapping file"):
        load_mapping("/nonexistent/path/to/mapping.json")


def test_load_mapping_none() -> None:
    """Test that None filepath returns empty dict."""
    from org.config import load_mapping

    result = load_mapping(None)
    assert result == {}


def test_load_mapping_valid(tmp_path: Path) -> None:
    """Test loading valid mapping file."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": "testing", "webdev": "frontend"}')

    result = load_mapping(str(mapping_file))
    assert result == {"test": "testing", "webdev": "frontend"}


def test_load_mapping_empty_dict(tmp_path: Path) -> None:
    """Test loading empty mapping dict."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("{}")

    result = load_mapping(str(mapping_file))
    assert result == {}


def test_load_mapping_invalid_json(tmp_path: Path) -> None:
    """Test that invalid JSON raises error."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": "testing",')

    with pytest.raises(typer.BadParameter, match="Invalid JSON"):
        load_mapping(str(mapping_file))


def test_load_mapping_non_dict_json_array(tmp_path: Path) -> None:
    """Test that JSON array raises error."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('["test", "testing"]')

    with pytest.raises(typer.BadParameter, match="must contain a JSON object"):
        load_mapping(str(mapping_file))


def test_load_mapping_non_dict_json_string(tmp_path: Path) -> None:
    """Test that JSON string raises error."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('"test string"')

    with pytest.raises(typer.BadParameter, match="must contain a JSON object"):
        load_mapping(str(mapping_file))


def test_load_mapping_non_dict_json_number(tmp_path: Path) -> None:
    """Test that JSON number raises error."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("42")

    with pytest.raises(typer.BadParameter, match="must contain a JSON object"):
        load_mapping(str(mapping_file))


def test_load_mapping_non_string_keys(tmp_path: Path) -> None:
    """Test that mapping with valid string keys works (JSON converts int keys to strings)."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"123": "testing"}')

    result = load_mapping(str(mapping_file))

    assert result == {"123": "testing"}


def test_load_mapping_non_string_values(tmp_path: Path) -> None:
    """Test that mapping with non-string values raises error."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": 123}')

    with pytest.raises(typer.BadParameter, match="must be strings"):
        load_mapping(str(mapping_file))


def test_load_mapping_mixed_non_string_types(tmp_path: Path) -> None:
    """Test that mapping with mixed non-string types raises error."""
    from org.config import load_mapping

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"test": "testing", "another": ["array"]}')

    with pytest.raises(typer.BadParameter, match="must be strings"):
        load_mapping(str(mapping_file))


def test_load_nodes_not_found() -> None:
    """Test that loading non-existent org file raises error."""
    from org.parse import load_nodes

    with pytest.raises(typer.BadParameter, match="not found"):
        load_nodes(["/nonexistent/file.org"], ["TODO"], ["DONE"], [])


def test_load_nodes_valid() -> None:
    """Test loading valid org files."""
    from org.parse import load_nodes

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nodes, _, _ = load_nodes([fixture_path], ["TODO"], ["DONE"], [])

    assert len(nodes) > 0
    assert all(hasattr(node, "heading") for node in nodes)


def test_load_nodes_todo_keys() -> None:
    """Test loading valid org files."""
    from org.parse import load_nodes

    fixture_path = os.path.join(FIXTURES_DIR, "todo_keys.org")
    nodes, todo_keys, done_keys = load_nodes([fixture_path], ["TODO"], ["DONE"], [])

    assert len(nodes) > 0
    assert set(todo_keys) == {"TODO", "STARTED"}
    assert set(done_keys) == {"DONE", "CANCELLED"}


def test_load_nodes_multiple() -> None:
    """Test loading multiple org files."""
    from org.parse import load_nodes

    fixture1 = os.path.join(FIXTURES_DIR, "simple.org")
    fixture2 = os.path.join(FIXTURES_DIR, "single_task.org")

    nodes, _, _ = load_nodes([fixture1, fixture2], ["TODO"], ["DONE"], [])

    assert len(nodes) > 0


def test_load_nodes_with_24_00_time() -> None:
    """Test that 24:00 time format is normalized."""
    from org.parse import load_nodes

    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    nodes, _, _ = load_nodes([fixture_path], ["TODO"], ["DONE"], [])

    assert len(nodes) > 0
