"""Tests for the clean() function."""

from orgstats.cli import DEFAULT_EXCLUDE
from orgstats.core import Frequency, clean


def freq_dict_from_ints(d: dict[str, int]) -> dict[str, Frequency]:
    """Convert dict[str, int] to dict[str, Frequency] for testing."""
    return {k: Frequency(v) for k, v in d.items()}


def freq_dict_to_ints(d: dict[str, Frequency]) -> dict[str, int]:
    """Convert dict[str, Frequency] to dict[str, int] for assertions."""
    return {k: v.total for k, v in d.items()}


def test_clean_basic():
    """Test basic filtering of tags."""
    disallowed = {"stop", "word"}
    tags = freq_dict_from_ints({"stop": 5, "word": 3, "keep": 10})
    result = clean(disallowed, tags)
    assert freq_dict_to_ints(result) == {"keep": 10}


def test_clean_removes_all_disallowed():
    """Test that all tags in disallowed set are removed."""
    disallowed = {"tag1", "tag2", "tag3"}
    tags = freq_dict_from_ints({"tag1": 1, "tag2": 2, "tag3": 3, "tag4": 4})
    result = clean(disallowed, tags)
    assert freq_dict_to_ints(result) == {"tag4": 4}


def test_clean_empty_disallowed():
    """Test clean with empty disallowed set."""
    disallowed = set()
    tags = freq_dict_from_ints({"tag1": 1, "tag2": 2})
    result = clean(disallowed, tags)
    assert freq_dict_to_ints(result) == {"tag1": 1, "tag2": 2}


def test_clean_empty_tags():
    """Test clean with empty tags dict."""
    disallowed = {"stop"}
    tags = {}
    result = clean(disallowed, tags)
    assert result == {}


def test_clean_no_overlap():
    """Test clean when disallowed and tags don't overlap."""
    disallowed = {"stop1", "stop2"}
    tags = freq_dict_from_ints({"keep1": 5, "keep2": 10})
    result = clean(disallowed, tags)
    assert freq_dict_to_ints(result) == {"keep1": 5, "keep2": 10}


def test_clean_all_filtered():
    """Test clean when all tags are in disallowed set."""
    disallowed = {"tag1", "tag2"}
    tags = {"tag1": 1, "tag2": 2}
    result = clean(disallowed, tags)
    assert result == {}


def test_clean_preserves_frequencies():
    """Test that clean preserves the frequency values."""
    disallowed = {"stop"}
    tags = freq_dict_from_ints({"stop": 100, "keep1": 42, "keep2": 99})
    result = clean(disallowed, tags)
    assert freq_dict_to_ints(result) == {"keep1": 42, "keep2": 99}


def test_clean_with_default_constant():
    """Test clean with the DEFAULT_EXCLUDE constant."""
    body_words = freq_dict_from_ints(
        {"end": 20, "logbook": 15, "implementation": 10, "algorithm": 5}
    )
    result = clean(DEFAULT_EXCLUDE, body_words)
    # "end" and "logbook" are in DEFAULT_EXCLUDE
    assert "end" not in result
    assert "logbook" not in result
    assert freq_dict_to_ints(result) == {"implementation": 10, "algorithm": 5}


def test_clean_returns_dict():
    """Test that clean returns a dictionary."""
    disallowed = {"stop"}
    tags = {"stop": 1, "keep": 2}
    result = clean(disallowed, tags)
    assert isinstance(result, dict)


def test_clean_zero_frequency():
    """Test clean with zero frequency tags."""
    disallowed = {"stop"}
    tags = freq_dict_from_ints({"stop": 0, "keep": 0, "another": 5})
    result = clean(disallowed, tags)
    assert freq_dict_to_ints(result) == {"keep": 0, "another": 5}


def test_clean_case_sensitive():
    """Test that clean is case-sensitive."""
    disallowed = {"stop"}
    tags = freq_dict_from_ints({"stop": 1, "Stop": 2, "STOP": 3})
    result = clean(disallowed, tags)
    # Only lowercase "stop" should be filtered
    assert "stop" not in result
    assert freq_dict_to_ints(result) == {"Stop": 2, "STOP": 3}
