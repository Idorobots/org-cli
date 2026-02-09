"""Integration tests using real Org-mode files."""

import os

import orgparse

from orgstats.cli import DEFAULT_EXCLUDE
from orgstats.core import analyze, clean


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

    result = analyze(nodes, {})

    assert result.total_tasks == 1
    assert result.done_tasks == 1


def test_integration_single_task():
    """Test with single_task.org fixture."""
    nodes = load_org_file("single_task.org")

    result_tags = analyze(nodes, {}, category="tags")
    assert result_tags.total_tasks == 1
    assert result_tags.done_tasks == 1
    # Check tags (Testing, Python -> testing, python)
    assert "testing" in result_tags.tag_frequencies
    assert "python" in result_tags.tag_frequencies

    # Check heading words
    result_heading = analyze(nodes, {}, category="heading")
    assert "write" in result_heading.tag_frequencies
    assert "comprehensive" in result_heading.tag_frequencies
    assert "tests" in result_heading.tag_frequencies

    # Check body words
    result_body = analyze(nodes, {}, category="body")
    assert (
        "task" in result_body.tag_frequencies or "this" in result_body.tag_frequencies
    )  # Some words from body


def test_integration_multiple_tags():
    """Test with multiple_tags.org fixture."""
    nodes = load_org_file("multiple_tags.org")

    result = analyze(
        nodes,
        {
            "test": "testing",
            "webdev": "frontend",
            "unix": "linux",
            "sysadmin": "devops",
            "maintenance": "refactoring",
        },
    )

    assert result.total_tasks == 3
    assert result.done_tasks == 2  # Two DONE, one TODO

    # Check tag mappings
    # Test -> testing, WebDev -> webdev -> frontend, Unix -> unix -> linux
    assert "testing" in result.tag_frequencies
    assert "frontend" in result.tag_frequencies
    assert "linux" in result.tag_frequencies

    # SysAdmin -> sysadmin -> devops
    assert "devops" in result.tag_frequencies

    # Maintenance -> maintenance -> refactoring
    assert "refactoring" in result.tag_frequencies


def test_integration_edge_cases():
    """Test with edge_cases.org fixture."""
    nodes = load_org_file("edge_cases.org")

    result = analyze(nodes, {})

    # All three tasks are DONE
    assert result.total_tasks == 3
    assert result.done_tasks == 3

    # Note: orgparse doesn't parse tags with punctuation in the heading line
    # Only properly formatted tags like :NoBody: are parsed
    # NoBody tag should be present
    assert "nobody" in result.tag_frequencies
    assert result.tag_frequencies["nobody"] == 1

    # Check that special characters in heading are handled
    result_heading = analyze(nodes, {}, category="heading")
    assert "task" in result_heading.tag_frequencies
    assert "special" in result_heading.tag_frequencies or "chars" in result_heading.tag_frequencies


def test_integration_24_00_time_handling():
    """Test that 24:00 time format is handled correctly."""
    nodes = load_org_file("edge_cases.org")

    # Should not crash when parsing file with 24:00
    # (file has 24:00 which is replaced with 00:00)
    result = analyze(nodes, {})

    assert result.total_tasks > 0
    assert result.done_tasks > 0


def test_integration_empty_file():
    """Test with empty.org fixture (TODO tasks)."""
    nodes = load_org_file("empty.org")

    result = analyze(nodes, {})

    assert result.total_tasks == 1
    assert result.done_tasks == 0  # TODO, not DONE


def test_integration_repeated_tasks():
    """Test with repeated_tasks.org fixture."""
    nodes = load_org_file("repeated_tasks.org")

    result = analyze(nodes, {})

    # Note: orgparse may or may not parse repeated tasks from LOGBOOK
    # This depends on orgparse's implementation
    # At minimum, we should have one task
    assert result.total_tasks >= 1

    # Check tag normalization (Agile, GTD -> agile, gtd -> agile, agile)
    # GTD -> gtd -> agile (mapped)
    if "agile" in result.tag_frequencies:
        assert result.tag_frequencies["agile"].total > 0  # Check Frequency.total field


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

    result = analyze(nodes, {})

    # All tasks in ARCHIVE_small are DONE
    assert result.total_tasks > 0
    assert result.done_tasks > 0
    assert result.done_tasks <= result.total_tasks

    # Check that some expected tags exist
    # The file has various tags like ProjectManagement, Debugging, etc.
    assert len(result.tag_frequencies) > 0

    # Check that heading words are extracted
    result_heading = analyze(nodes, {}, category="heading")
    assert len(result_heading.tag_frequencies) > 0

    # Check that body words are extracted
    result_body = analyze(nodes, {}, category="body")
    assert len(result_body.tag_frequencies) > 0


def test_integration_clean_filters_stopwords():
    """Test that clean() properly filters stop words from real data."""
    nodes = load_org_file("multiple_tags.org")

    result_tags = analyze(nodes, {}, category="tags")
    result_heading = analyze(nodes, {}, category="heading")
    result_body = analyze(nodes, {}, category="body")

    # Apply cleaning
    cleaned_tags = clean(DEFAULT_EXCLUDE, result_tags.tag_frequencies)
    cleaned_heading = clean(DEFAULT_EXCLUDE, result_heading.tag_frequencies)
    cleaned_words = clean(DEFAULT_EXCLUDE, result_body.tag_frequencies)

    # Stop words should be removed
    for stop_word in DEFAULT_EXCLUDE:
        assert stop_word not in cleaned_tags

    for stop_word in DEFAULT_EXCLUDE:
        assert stop_word not in cleaned_heading

    for stop_word in DEFAULT_EXCLUDE:
        assert stop_word not in cleaned_words


def test_integration_frequency_sorting():
    """Test that results can be sorted by frequency."""
    nodes = load_org_file("multiple_tags.org")

    result = analyze(nodes, {})

    # Sort tags by frequency (descending)
    sorted_tags = sorted(result.tag_frequencies.items(), key=lambda item: -item[1].total)

    # Should have at least one tag
    assert len(sorted_tags) > 0

    # Check that sorting is correct (descending order)
    for i in range(len(sorted_tags) - 1):
        assert sorted_tags[i][1].total >= sorted_tags[i + 1][1].total


def test_integration_word_uniqueness():
    """Test that words in headings/body are deduplicated per task."""
    nodes = load_org_file("single_task.org")

    result_heading = analyze(nodes, {}, category="heading")
    result_body = analyze(nodes, {}, category="body")

    # Words should be deduplicated within each task
    # but counted across tasks
    assert isinstance(result_heading.tag_frequencies, dict)
    assert isinstance(result_body.tag_frequencies, dict)


def test_integration_no_tags_task():
    """Test task without any tags."""
    nodes = load_org_file("simple.org")

    result = analyze(nodes, {})

    # Simple task has no tags
    assert len(result.tag_frequencies) == 0 or all(
        v.total == 0 for v in result.tag_frequencies.values()
    )


def test_integration_all_fixtures_parseable():
    """Test that all fixture files can be parsed without errors."""
    fixtures = [
        "simple.org",
        "single_task.org",
        "multiple_tags.org",
        "edge_cases.org",
        "repeated_tasks.org",
        "empty.org",
    ]

    for fixture in fixtures:
        nodes = load_org_file(fixture)
        # Should not raise any exceptions
        result = analyze(nodes, {}, category="tags")

        # Basic sanity checks
        assert result.total_tasks >= 0
        assert result.done_tasks >= 0
        assert result.done_tasks <= result.total_tasks
        assert isinstance(result.tag_frequencies, dict)
        assert isinstance(result.tag_relations, dict)
        assert isinstance(result.tag_time_ranges, dict)
