"""Tests for the normalize() function."""

from org.analyze import normalize


def test_normalize_basic() -> None:
    """Test basic tag normalization."""
    tags = {"Testing", "Python"}
    result = normalize(tags, {})
    assert "testing" in result
    assert "python" in result


def test_normalize_lowercasing() -> None:
    """Test that tags are lowercased."""
    tags = {"UPPERCASE", "MixedCase", "lowercase"}
    result = normalize(tags, {})
    assert result == {"uppercase", "mixedcase", "lowercase"}


def test_normalize_strips_whitespace() -> None:
    """Test that whitespace is stripped."""
    tags = {" spaces ", "  tabs\t", "\nNewline"}
    result = normalize(tags, {})
    assert "spaces" in result
    assert "tabs" in result
    assert "newline" in result


def test_normalize_removes_punctuation() -> None:
    """Test that punctuation is removed."""
    tags = {
        "tag.with.dots",
        "tag:with:colons",
        "tag!exclaim",
        "tag,comma",
        "tag;semicolon",
        "tag?question",
    }
    result = normalize(tags, {})
    assert "tagwithdots" in result
    assert "tagwithcolons" in result
    assert "tagexclaim" in result
    assert "tagcomma" in result
    assert "tagsemicolon" in result
    assert "tagquestion" in result


def test_normalize_applies_mapping() -> None:
    """Test that tags are mapped to canonical forms."""
    tags = {"test", "sysadmin", "unix", "webdev"}
    result = normalize(
        tags, {"test": "testing", "sysadmin": "devops", "unix": "linux", "webdev": "frontend"}
    )
    assert "testing" in result
    assert "devops" in result
    assert "linux" in result
    assert "frontend" in result


def test_normalize_unmapped_tags_unchanged() -> None:
    """Test that unmapped tags remain unchanged."""
    tags = {"unmapped", "custom"}
    result = normalize(tags, {})
    assert "unmapped" in result
    assert "custom" in result


def test_normalize_empty_set() -> None:
    """Test normalizing an empty set."""
    tags: set[str] = set()
    result = normalize(tags, {})
    assert result == set()


def test_normalize_single_tag() -> None:
    """Test normalizing a single tag."""
    tags = {"SingleTag"}
    result = normalize(tags, {})
    assert result == {"singletag"}


def test_normalize_complex_scenario() -> None:
    """Test normalization with multiple transformations."""
    tags = {"Test.", ":SysAdmin:", "  UNIX  ", "webdev!"}
    result = normalize(
        tags, {"test": "testing", "webdev": "frontend", "sysadmin": "devops", "unix": "linux"}
    )
    # test. -> test -> testing (mapped)
    # :sysadmin: -> sysadmin -> devops (mapped)
    # unix -> linux (mapped)
    # webdev! -> webdev -> frontend (mapped)
    assert "testing" in result
    assert "devops" in result
    assert "linux" in result
    assert "frontend" in result


def test_normalize_all_map_entries() -> None:
    """Test that all entries in MAP are properly applied."""
    # Test a few key mappings from the MAP dictionary
    test_cases = {
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
    }

    for original, expected in test_cases.items():
        result = normalize({original}, test_cases)
        assert expected in result, f"Expected {original} to map to {expected}"


def test_normalize_preserves_set_type() -> None:
    """Test that normalize returns a set."""
    tags = {"tag1", "tag2"}
    result = normalize(tags, {})
    assert isinstance(result, set)


def test_normalize_handles_duplicate_normalization() -> None:
    """Test that multiple tags normalizing to the same value result in one entry."""
    tags = {"test", "Test", "TEST"}
    result = normalize(tags, {"test": "testing"})
    # All should normalize to "test" then map to "testing"
    assert len(result) == 1
    assert "testing" in result


def test_normalize_empty_string() -> None:
    """Test normalizing tags including empty string."""
    tags = {"", "valid"}
    result = normalize(tags, {})
    assert "" in result
    assert "valid" in result


def test_normalize_with_custom_mapping() -> None:
    """Test normalize with custom mapping parameter."""
    custom_map = {"foo": "bar", "baz": "qux"}
    tags = {"foo", "baz", "unmapped"}
    result = normalize(tags, custom_map)
    assert "bar" in result
    assert "qux" in result
    assert "unmapped" in result


def test_normalize_with_empty_mapping() -> None:
    """Test normalize with empty mapping (no transformations)."""
    empty_map: dict[str, str] = {}
    tags = {"test", "sysadmin"}
    result = normalize(tags, empty_map)
    assert "test" in result
    assert "sysadmin" in result


def test_normalize_default_mapping_parameter() -> None:
    """Test that default mapping parameter uses MAP."""
    tags = {"test", "sysadmin"}
    result = normalize(tags, {"test": "testing", "sysadmin": "devops"})
    assert "testing" in result
    assert "devops" in result
