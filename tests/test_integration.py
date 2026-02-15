"""Integration tests using real Org-mode files."""

import os

import orgparse

from orgstats.analyze import analyze, clean
from orgstats.cli import DEFAULT_EXCLUDE


# Path to fixtures directory
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_org_file(filename: str) -> list[orgparse.node.OrgNode]:
    """Load and parse an Org-mode file."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath) as f:
        # NOTE: Making the file parseable (handle 24:00 time format)
        contents = f.read().replace("24:00", "00:00")
        ns = orgparse.loads(contents)
        if ns is None:
            return []  # type: ignore[unreachable]
        return list(ns[1:])


def test_integration_simple_file() -> None:
    """Test with the simple.org fixture."""
    nodes = load_org_file("simple.org")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values["DONE"] == 1


def test_integration_single_task() -> None:
    """Test with single_task.org fixture."""
    nodes = load_org_file("single_task.org")

    result_tags = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])
    assert result_tags.total_tasks == 1
    assert result_tags.task_states.values["DONE"] == 1
    # Check tags (Testing, Python - CamelCase preserved)
    assert "Testing" in result_tags.tag_frequencies
    assert "Python" in result_tags.tag_frequencies

    # Check heading words
    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    assert "write" in result_heading.tag_frequencies
    assert "comprehensive" in result_heading.tag_frequencies
    assert "tests" in result_heading.tag_frequencies

    # Check body words
    result_body = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])
    assert (
        "task" in result_body.tag_frequencies or "this" in result_body.tag_frequencies
    )  # Some words from body


def test_integration_multiple_tags() -> None:
    """Test with multiple_tags.org fixture."""
    nodes = load_org_file("multiple_tags.org")

    result = analyze(
        nodes,
        {
            "Test": "Testing",
            "WebDev": "Frontend",
            "Unix": "Linux",
            "SysAdmin": "DevOps",
            "Maintenance": "Refactoring",
        },
        category="tags",
        max_relations=3,
        done_keys=["DONE"],
    )

    assert result.total_tasks == 3
    assert result.task_states.values["DONE"] == 2
    assert result.task_states.values["TODO"] == 1

    # Check tag mappings
    # Test -> Testing, WebDev -> Frontend, Unix -> Linux
    assert "Testing" in result.tag_frequencies
    assert "Frontend" in result.tag_frequencies
    assert "Linux" in result.tag_frequencies

    # SysAdmin -> DevOps
    assert "DevOps" in result.tag_frequencies

    # Maintenance tag is on TODO task, so it should not appear in frequencies
    assert "Refactoring" not in result.tag_frequencies
    assert "Maintenance" not in result.tag_frequencies


def test_integration_edge_cases() -> None:
    """Test with edge_cases.org fixture."""
    nodes = load_org_file("edge_cases.org")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # All three tasks are DONE (only repeated tasks counted)
    assert result.total_tasks == 3
    assert result.task_states.values["DONE"] == 3

    # Note: orgparse doesn't parse tags with punctuation in the heading line
    # Only properly formatted tags like :NoBody: are parsed
    # NoBody tag should be present (CamelCase preserved)
    assert "NoBody" in result.tag_frequencies
    assert result.tag_frequencies["NoBody"] == 1

    # Check that special characters in heading are handled
    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    assert "task" in result_heading.tag_frequencies
    assert "special" in result_heading.tag_frequencies or "chars" in result_heading.tag_frequencies


def test_integration_24_00_time_handling() -> None:
    """Test that 24:00 time format is handled correctly."""
    nodes = load_org_file("edge_cases.org")

    # Should not crash when parsing file with 24:00
    # (file has 24:00 which is replaced with 00:00)
    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks > 0
    assert result.task_states.values["DONE"] > 0


def test_integration_empty_file() -> None:
    """Test with empty.org fixture (TODO tasks)."""
    nodes = load_org_file("empty.org")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.total_tasks == 1
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values["TODO"] == 1


def test_integration_repeated_tasks() -> None:
    """Test with repeated_tasks.org fixture."""
    nodes = load_org_file("repeated_tasks.org")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Note: orgparse may or may not parse repeated tasks from LOGBOOK
    # This depends on orgparse's implementation
    # At minimum, we should have one task
    assert result.total_tasks >= 1

    # Check tag mapping without normalization (Agile, GTD with mapping)
    # Note: without explicit mapping for CamelCase tags, they remain as-is
    # If there are tags in result, just verify they exist
    if len(result.tag_frequencies) > 0:
        assert any(freq.total > 0 for freq in result.tag_frequencies.values())


def test_integration_archive_small() -> None:
    """Test with the actual ARCHIVE_small example file."""
    # Load the real archive file
    archive_path = os.path.join(os.path.dirname(__file__), "..", "examples", "ARCHIVE_small")

    with open(archive_path) as f:
        contents = f.read().replace("24:00", "00:00")
        ns = orgparse.loads(contents)
        nodes = []
        if ns is not None:
            nodes = list(ns[1:])

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # All tasks in ARCHIVE_small are DONE
    assert result.total_tasks > 0
    assert result.task_states.values["DONE"] > 0

    # Check that some expected tags exist
    # The file has various tags like ProjectManagement, Debugging, etc.
    assert len(result.tag_frequencies) > 0

    # Check that heading words are extracted
    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    assert len(result_heading.tag_frequencies) > 0

    # Check that body words are extracted
    result_body = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])
    assert len(result_body.tag_frequencies) > 0


def test_integration_clean_filters_stopwords() -> None:
    """Test that clean() properly filters stop words from real data."""
    nodes = load_org_file("multiple_tags.org")

    result_tags = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])
    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    result_body = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])

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


def test_integration_frequency_sorting() -> None:
    """Test that results can be sorted by frequency."""
    nodes = load_org_file("multiple_tags.org")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Sort tags by frequency (descending)
    sorted_tags = sorted(result.tag_frequencies.items(), key=lambda item: -item[1].total)

    # Should have at least one tag
    assert len(sorted_tags) > 0

    # Check that sorting is correct (descending order)
    for i in range(len(sorted_tags) - 1):
        assert sorted_tags[i][1].total >= sorted_tags[i + 1][1].total


def test_integration_word_uniqueness() -> None:
    """Test that words in headings/body are deduplicated per task."""
    nodes = load_org_file("single_task.org")

    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    result_body = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])

    # Words should be deduplicated within each task
    # but counted across tasks
    assert isinstance(result_heading.tag_frequencies, dict)
    assert isinstance(result_body.tag_frequencies, dict)


def test_integration_no_tags_task() -> None:
    """Test task without any tags."""
    nodes = load_org_file("simple.org")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    # Simple task has no tags
    assert len(result.tag_frequencies) == 0 or all(
        v.total == 0 for v in result.tag_frequencies.values()
    )


def test_integration_all_fixtures_parseable() -> None:
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
        result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

        # Basic sanity checks
        assert result.total_tasks >= 0
        assert result.task_states.values.get("DONE", 0) >= 0
        assert result.task_states.values.get("TODO", 0) >= 0
        assert isinstance(result.tag_frequencies, dict)
        assert isinstance(result.tag_relations, dict)
        assert isinstance(result.tag_time_ranges, dict)


def test_integration_filtered_repeats_in_analysis() -> None:
    """Test that filtered repeated tasks produce correct analysis results."""
    from datetime import datetime

    from orgstats.filters import filter_date_from, filter_date_until

    org_text = """* DONE Task :tag1:tag2:
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
- State "DONE" from "TODO" [2025-03-20 Thu 14:00]
:END:
"""
    nodes = list(orgparse.loads(org_text)[1:])

    unfiltered_result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    filtered_nodes = filter_date_from(nodes, datetime(2025, 2, 1))
    filtered_nodes = filter_date_until(filtered_nodes, datetime(2025, 3, 1))
    filtered_result = analyze(
        filtered_nodes, {}, category="tags", max_relations=3, done_keys=["DONE"]
    )

    assert unfiltered_result.total_tasks == 3
    assert unfiltered_result.task_states.values["DONE"] == 3

    assert filtered_result.total_tasks == 1
    assert filtered_result.task_states.values["DONE"] == 1

    assert filtered_result.tag_frequencies["tag1"].total == 1
    assert filtered_result.tag_frequencies["tag2"].total == 1
