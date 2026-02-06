"""Tests for the mapped() function."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import mapped, MAP


def test_mapped_found_in_mapping():
    """Test that mapped returns the canonical form when tag is in mapping."""
    result = mapped(MAP, "test")
    assert result == "testing"


def test_mapped_not_found_returns_original():
    """Test that mapped returns the original tag when not in mapping."""
    result = mapped(MAP, "nonexistent")
    assert result == "nonexistent"


def test_mapped_all_map_entries():
    """Test all entries in the MAP dictionary."""
    expected_mappings = {
        "test": "testing",
        "sysadmin": "devops",
        "pldesign": "compilers",
        "webdev": "frontend",
        "unix": "linux",
        "gtd": "agile",
        "foof": "spartan",
        "typing": "documenting",
        "notestaking": "documenting",
        "computernetworks": "networking",
        "maintenance": "refactoring",
        "softwareengineering": "softwarearchitecture",
        "soa": "softwarearchitecture",
        "uml": "softwarearchitecture",
        "dia": "softwarearchitecture",
    }
    
    for key, value in expected_mappings.items():
        result = mapped(MAP, key)
        assert result == value, f"Expected mapped(MAP, '{key}') to return '{value}', got '{result}'"


def test_mapped_empty_string():
    """Test mapped with empty string."""
    result = mapped(MAP, "")
    assert result == ""


def test_mapped_custom_mapping():
    """Test mapped with a custom mapping dictionary."""
    custom_map = {"foo": "bar", "baz": "qux"}
    
    assert mapped(custom_map, "foo") == "bar"
    assert mapped(custom_map, "baz") == "qux"
    assert mapped(custom_map, "unknown") == "unknown"


def test_mapped_empty_mapping():
    """Test mapped with an empty mapping dictionary."""
    empty_map = {}
    result = mapped(empty_map, "anything")
    assert result == "anything"


def test_mapped_case_sensitive():
    """Test that mapped is case-sensitive."""
    # MAP has lowercase keys
    result_lower = mapped(MAP, "test")
    result_upper = mapped(MAP, "TEST")
    
    assert result_lower == "testing"  # Found in map
    assert result_upper == "TEST"     # Not found, returns original


def test_mapped_whitespace():
    """Test mapped with whitespace in tag."""
    result = mapped(MAP, " test ")
    assert result == " test "  # Not found with whitespace, returns original


def test_mapped_preserves_type():
    """Test that mapped returns a string."""
    result = mapped(MAP, "test")
    assert isinstance(result, str)
