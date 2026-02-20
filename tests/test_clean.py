"""Tests for the clean() function."""

from orgstats.analyze import Frequency, Relations, Tag, TimeRange, clean
from orgstats.cli import DEFAULT_EXCLUDE


def tag_dict_from_ints(d: dict[str, int]) -> dict[str, Tag]:
    """Convert dict[str, int] to dict[str, Tag] for testing."""
    return {
        k: Tag(
            name=k,
            frequency=Frequency(v),
            relations=Relations(name=k, relations={}),
            time_range=TimeRange(),
            total_tasks=v,
            avg_tasks_per_day=0.0,
            max_single_day_count=0,
        )
        for k, v in d.items()
    }


def tag_dict_to_ints(d: dict[str, Tag]) -> dict[str, int]:
    """Convert dict[str, Tag] to dict[str, int] for assertions."""
    return {k: v.frequency.total for k, v in d.items()}


def test_clean_basic() -> None:
    """Test basic filtering of tags."""
    disallowed = {"stop", "word"}
    tags = tag_dict_from_ints({"stop": 5, "word": 3, "keep": 10})
    result = clean(disallowed, tags)
    assert tag_dict_to_ints(result) == {"keep": 10}


def test_clean_removes_all_disallowed() -> None:
    """Test that all tags in disallowed set are removed."""
    disallowed = {"tag1", "tag2", "tag3"}
    tags = tag_dict_from_ints({"tag1": 1, "tag2": 2, "tag3": 3, "tag4": 4})
    result = clean(disallowed, tags)
    assert tag_dict_to_ints(result) == {"tag4": 4}


def test_clean_empty_disallowed() -> None:
    """Test clean with empty disallowed set."""
    disallowed: set[str] = set()
    tags = tag_dict_from_ints({"tag1": 1, "tag2": 2})
    result = clean(disallowed, tags)
    assert tag_dict_to_ints(result) == {"tag1": 1, "tag2": 2}


def test_clean_empty_tags() -> None:
    """Test clean with empty tags dict."""
    disallowed = {"stop"}
    tags: dict[str, Tag] = {}
    result = clean(disallowed, tags)
    assert result == {}


def test_clean_no_overlap() -> None:
    """Test clean when disallowed and tags don't overlap."""
    disallowed = {"stop1", "stop2"}
    tags = tag_dict_from_ints({"keep1": 5, "keep2": 10})
    result = clean(disallowed, tags)
    assert tag_dict_to_ints(result) == {"keep1": 5, "keep2": 10}


def test_clean_all_filtered() -> None:
    """Test clean when all tags are in disallowed set."""
    disallowed = {"tag1", "tag2"}
    tags = tag_dict_from_ints({"tag1": 1, "tag2": 2})
    result = clean(disallowed, tags)
    assert result == {}


def test_clean_preserves_frequencies() -> None:
    """Test that clean preserves the frequency values."""
    disallowed = {"stop"}
    tags = tag_dict_from_ints({"stop": 100, "keep1": 42, "keep2": 99})
    result = clean(disallowed, tags)
    assert tag_dict_to_ints(result) == {"keep1": 42, "keep2": 99}


def test_clean_with_default_constant() -> None:
    """Test clean with the DEFAULT_EXCLUDE constant."""
    body_words = tag_dict_from_ints(
        {"end": 20, "logbook": 15, "implementation": 10, "algorithm": 5}
    )
    result = clean(DEFAULT_EXCLUDE, body_words)
    # "end" and "logbook" are in DEFAULT_EXCLUDE
    assert "end" not in result
    assert "logbook" not in result
    assert tag_dict_to_ints(result) == {"implementation": 10, "algorithm": 5}


def test_clean_returns_dict() -> None:
    """Test that clean returns a dictionary."""
    disallowed = {"stop"}
    tags = tag_dict_from_ints({"stop": 1, "keep": 2})
    result = clean(disallowed, tags)
    assert isinstance(result, dict)


def test_clean_zero_frequency() -> None:
    """Test clean with zero frequency tags."""
    disallowed = {"stop"}
    tags = tag_dict_from_ints({"stop": 0, "keep": 0, "another": 5})
    result = clean(disallowed, tags)
    assert tag_dict_to_ints(result) == {"keep": 0, "another": 5}


def test_clean_case_sensitive() -> None:
    """Test that clean is case-insensitive."""
    disallowed = {"stop"}
    tags = tag_dict_from_ints({"stop": 1, "Stop": 2, "STOP": 3})
    result = clean(disallowed, tags)
    # All variants of "stop" should be filtered (case-insensitive)
    assert "stop" not in result
    assert "Stop" not in result
    assert "STOP" not in result
    assert tag_dict_to_ints(result) == {}
