"""Tests for the clean() function."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import clean, TAGS, HEADING, WORDS


def test_clean_basic():
    """Test basic filtering of tags."""
    allowed = {"stop", "word"}
    tags = {"stop": 5, "word": 3, "keep": 10}
    result = clean(allowed, tags)
    assert result == {"keep": 10}


def test_clean_removes_all_allowed():
    """Test that all tags in allowed set are removed."""
    allowed = {"tag1", "tag2", "tag3"}
    tags = {"tag1": 1, "tag2": 2, "tag3": 3, "tag4": 4}
    result = clean(allowed, tags)
    assert result == {"tag4": 4}


def test_clean_empty_allowed():
    """Test clean with empty allowed set."""
    allowed = set()
    tags = {"tag1": 1, "tag2": 2}
    result = clean(allowed, tags)
    assert result == {"tag1": 1, "tag2": 2}


def test_clean_empty_tags():
    """Test clean with empty tags dict."""
    allowed = {"stop"}
    tags = {}
    result = clean(allowed, tags)
    assert result == {}


def test_clean_no_overlap():
    """Test clean when allowed and tags don't overlap."""
    allowed = {"stop1", "stop2"}
    tags = {"keep1": 5, "keep2": 10}
    result = clean(allowed, tags)
    assert result == {"keep1": 5, "keep2": 10}


def test_clean_all_filtered():
    """Test clean when all tags are in allowed set."""
    allowed = {"tag1", "tag2"}
    tags = {"tag1": 1, "tag2": 2}
    result = clean(allowed, tags)
    assert result == {}


def test_clean_preserves_frequencies():
    """Test that clean preserves the frequency values."""
    allowed = {"stop"}
    tags = {"stop": 100, "keep1": 42, "keep2": 99}
    result = clean(allowed, tags)
    assert result == {"keep1": 42, "keep2": 99}


def test_clean_with_tags_constant():
    """Test clean with the TAGS constant."""
    # TAGS contains stop words that should be filtered
    tags = {"comp": 5, "computer": 3, "programming": 10, "debugging": 8}
    result = clean(TAGS, tags)
    # comp and computer are in TAGS
    assert "comp" not in result
    assert "computer" not in result
    assert result == {"programming": 10, "debugging": 8}


def test_clean_with_heading_constant():
    """Test clean with the HEADING constant."""
    heading_words = {"the": 50, "to": 30, "implement": 10, "feature": 8}
    result = clean(HEADING, heading_words)
    # "the" and "to" are in HEADING
    assert "the" not in result
    assert "to" not in result
    assert result == {"implement": 10, "feature": 8}


def test_clean_with_words_constant():
    """Test clean with the WORDS constant."""
    body_words = {"end": 20, "logbook": 15, "implementation": 10, "algorithm": 5}
    result = clean(WORDS, body_words)
    # "end" and "logbook" are in WORDS
    assert "end" not in result
    assert "logbook" not in result
    assert result == {"implementation": 10, "algorithm": 5}


def test_clean_returns_dict():
    """Test that clean returns a dictionary."""
    allowed = {"stop"}
    tags = {"stop": 1, "keep": 2}
    result = clean(allowed, tags)
    assert isinstance(result, dict)


def test_clean_zero_frequency():
    """Test clean with zero frequency tags."""
    allowed = {"stop"}
    tags = {"stop": 0, "keep": 0, "another": 5}
    result = clean(allowed, tags)
    assert result == {"keep": 0, "another": 5}


def test_clean_case_sensitive():
    """Test that clean is case-sensitive."""
    allowed = {"stop"}
    tags = {"stop": 1, "Stop": 2, "STOP": 3}
    result = clean(allowed, tags)
    # Only lowercase "stop" should be filtered
    assert "stop" not in result
    assert result == {"Stop": 2, "STOP": 3}
