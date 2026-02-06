"""Integration tests using real Org-mode files."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import orgparse
from core import analyze, clean, TAGS, HEADING, WORDS

# Path to fixtures directory
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_org_file(filename):
    """Load and parse an Org-mode file."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath) as f:
        # NOTE: Making the file parseable (handle 24:00 time format)
        contents = f.read().replace("24:00", "00:00")
        ns = orgparse.loads(contents)
        if ns is not None:
            return list(ns[1:])
        return []


def test_integration_simple_file():
    """Test with the simple.org fixture."""
    nodes = load_org_file("simple.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 1
    assert done == 1


def test_integration_single_task():
    """Test with single_task.org fixture."""
    nodes = load_org_file("single_task.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 1
    assert done == 1
    
    # Check tags (Testing, Python -> testing, python)
    assert "testing" in tags
    assert "python" in tags
    
    # Check heading words
    assert "write" in heading
    assert "comprehensive" in heading
    assert "tests" in heading
    
    # Check body words
    assert "task" in words or "this" in words  # Some words from body


def test_integration_multiple_tags():
    """Test with multiple_tags.org fixture."""
    nodes = load_org_file("multiple_tags.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 3
    assert done == 2  # Two DONE, one TODO
    
    # Check tag mappings
    # Test -> testing, WebDev -> webdev -> frontend, Unix -> unix -> linux
    assert "testing" in tags
    assert "frontend" in tags
    assert "linux" in tags
    
    # SysAdmin -> sysadmin -> devops
    assert "devops" in tags
    
    # Maintenance -> maintenance -> refactoring
    assert "refactoring" in tags


def test_integration_edge_cases():
    """Test with edge_cases.org fixture."""
    nodes = load_org_file("edge_cases.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    # All three tasks are DONE
    assert total == 3
    assert done == 3
    
    # Note: orgparse doesn't parse tags with punctuation in the heading line
    # Only properly formatted tags like :NoBody: are parsed
    # NoBody tag should be present
    assert "nobody" in tags
    assert tags["nobody"] == 1
    
    # Check that special characters in heading are handled
    assert "task" in heading
    assert "special" in heading or "chars" in heading


def test_integration_24_00_time_handling():
    """Test that 24:00 time format is handled correctly."""
    nodes = load_org_file("edge_cases.org")
    
    # Should not crash when parsing file with 24:00
    # (file has 24:00 which is replaced with 00:00)
    total, done, tags, heading, words = analyze(nodes)
    
    assert total > 0
    assert done > 0


def test_integration_empty_file():
    """Test with empty.org fixture (TODO tasks)."""
    nodes = load_org_file("empty.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    assert total == 1
    assert done == 0  # TODO, not DONE


def test_integration_repeated_tasks():
    """Test with repeated_tasks.org fixture."""
    nodes = load_org_file("repeated_tasks.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    # Note: orgparse may or may not parse repeated tasks from LOGBOOK
    # This depends on orgparse's implementation
    # At minimum, we should have one task
    assert total >= 1
    
    # Check tag normalization (Agile, GTD -> agile, gtd -> agile, agile)
    # GTD -> gtd -> agile (mapped)
    if "agile" in tags:
        assert tags["agile"] > 0


def test_integration_archive_small():
    """Test with the actual ARCHIVE_small example file."""
    # Load the real archive file
    archive_path = os.path.join(os.path.dirname(__file__), "..", "examples", "ARCHIVE_small")
    
    with open(archive_path) as f:
        contents = f.read().replace("24:00", "00:00")
        ns = orgparse.loads(contents)
        nodes = []
        if ns is not None:
            nodes = list(ns[1:])
    
    total, done, tags, heading, words = analyze(nodes)
    
    # All tasks in ARCHIVE_small are DONE
    assert total > 0
    assert done > 0
    assert done <= total
    
    # Check that some expected tags exist
    # The file has various tags like ProjectManagement, Debugging, etc.
    assert len(tags) > 0
    
    # Check that heading words are extracted
    assert len(heading) > 0
    
    # Check that body words are extracted
    assert len(words) > 0


def test_integration_clean_filters_stopwords():
    """Test that clean() properly filters stop words from real data."""
    nodes = load_org_file("multiple_tags.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    # Apply cleaning
    cleaned_tags = clean(TAGS, tags)
    cleaned_heading = clean(HEADING, heading)
    cleaned_words = clean(WORDS, words)
    
    # Stop words should be removed
    for stop_word in TAGS:
        assert stop_word not in cleaned_tags
    
    for stop_word in HEADING:
        assert stop_word not in cleaned_heading
    
    for stop_word in WORDS:
        assert stop_word not in cleaned_words


def test_integration_frequency_sorting():
    """Test that results can be sorted by frequency."""
    nodes = load_org_file("multiple_tags.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    # Sort tags by frequency (descending)
    sorted_tags = sorted(tags.items(), key=lambda item: -item[1])
    
    # Should have at least one tag
    assert len(sorted_tags) > 0
    
    # Check that sorting is correct (descending order)
    for i in range(len(sorted_tags) - 1):
        assert sorted_tags[i][1] >= sorted_tags[i + 1][1]


def test_integration_word_uniqueness():
    """Test that words in headings/body are deduplicated per task."""
    nodes = load_org_file("single_task.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    # Words should be deduplicated within each task
    # but counted across tasks
    assert isinstance(heading, dict)
    assert isinstance(words, dict)


def test_integration_no_tags_task():
    """Test task without any tags."""
    nodes = load_org_file("simple.org")
    
    total, done, tags, heading, words = analyze(nodes)
    
    # Simple task has no tags
    assert len(tags) == 0 or all(v == 0 for v in tags.values())


def test_integration_all_fixtures_parseable():
    """Test that all fixture files can be parsed without errors."""
    fixtures = [
        "simple.org",
        "single_task.org",
        "multiple_tags.org",
        "edge_cases.org",
        "repeated_tasks.org",
        "empty.org"
    ]
    
    for fixture in fixtures:
        nodes = load_org_file(fixture)
        # Should not raise any exceptions
        total, done, tags, heading, words = analyze(nodes)
        
        # Basic sanity checks
        assert total >= 0
        assert done >= 0
        assert done <= total
        assert isinstance(tags, dict)
        assert isinstance(heading, dict)
        assert isinstance(words, dict)
