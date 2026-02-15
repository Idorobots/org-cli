"""Tests for the mapped() function."""

from orgstats.core import mapped


def test_mapped_found_in_mapping() -> None:
    """Test that mapped returns the canonical form when tag is in mapping."""
    mapping = {"Test": "Testing"}
    result = mapped(mapping, "Test")
    assert result == "Testing"


def test_mapped_not_found_returns_original() -> None:
    """Test that mapped returns the original tag when not in mapping."""
    mapping = {"Test": "Testing"}
    result = mapped(mapping, "nonexistent")
    assert result == "nonexistent"


def test_mapped_all_map_entries() -> None:
    """Test all entries in the MAP dictionary."""
    expected_mappings = {
        "Test": "Testing",
        "SysAdmin": "DevOps",
        "PLDesign": "Compilers",
        "WebDev": "Frontend",
        "Unix": "Linux",
        "GTD": "Agile",
        "Foof": "Spartan",
        "Typing": "Documenting",
        "NotesTaking": "Documenting",
        "ComputerNetworks": "Networking",
        "Maintenance": "Refactoring",
        "SoftwareEngineering": "SoftwareArchitecture",
        "SOA": "SoftwareArchitecture",
        "UML": "SoftwareArchitecture",
        "Dia": "SoftwareArchitecture",
    }

    for key, value in expected_mappings.items():
        result = mapped(expected_mappings, key)
        assert result == value, f"Expected mapped(MAP, '{key}') to return '{value}', got '{result}'"


def test_mapped_empty_string() -> None:
    """Test mapped with empty string."""
    mapping = {"Test": "Testing"}
    result = mapped(mapping, "")
    assert result == ""


def test_mapped_custom_mapping() -> None:
    """Test mapped with a custom mapping dictionary."""
    custom_map = {"foo": "bar", "baz": "qux"}

    assert mapped(custom_map, "foo") == "bar"
    assert mapped(custom_map, "baz") == "qux"
    assert mapped(custom_map, "unknown") == "unknown"


def test_mapped_empty_mapping() -> None:
    """Test mapped with an empty mapping dictionary."""
    empty_map: dict[str, str] = {}
    result = mapped(empty_map, "anything")
    assert result == "anything"


def test_mapped_case_sensitive() -> None:
    """Test that mapped is case-sensitive."""
    mapping = {"test": "testing", "Test": "Testing"}
    # MAP has both CamelCase and lowercase keys
    result_camel = mapped(mapping, "Test")
    result_upper = mapped(mapping, "TEST")
    result_lower = mapped(mapping, "test")

    assert result_camel == "Testing"  # Found in map
    assert result_upper == "TEST"  # Not found, returns original
    assert result_lower == "testing"  # Found in map (lowercase version)


def test_mapped_whitespace() -> None:
    """Test mapped with whitespace in tag."""
    mapping = {"Test": "Testing"}
    result = mapped(mapping, " Test ")
    assert result == " Test "  # Not found with whitespace, returns original


def test_mapped_preserves_type() -> None:
    """Test that mapped returns a string."""
    mapping = {"Test": "Testing"}
    result = mapped(mapping, "Test")
    assert isinstance(result, str)
