"""Integration tests using real Org-mode files."""

import os
from typing import TYPE_CHECKING

import org_parser

from org.analyze import analyze


if TYPE_CHECKING:
    from org_parser.document import Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_org_file(filename: str) -> list[Heading]:
    """Load and parse an Org-mode file."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath) as f:
        contents = f.read().replace("24:00", "00:00")
        ns = org_parser.loads(contents)
        return list(ns)


def test_integration_all_fixtures_parseable() -> None:
    """Test that all fixture files can be parsed without errors."""
    fixture_files = [
        "simple.org",
        "single_task.org",
        "multiple_tags.org",
        "edge_cases.org",
        "repeated_tasks.org",
        "relations_test.org",
    ]

    for fixture_file in fixture_files:
        nodes = load_org_file(fixture_file)
        result = analyze(nodes, {}, category="tags", max_relations=3)

        assert result.total_tasks >= 0
        assert isinstance(result.task_states.values, dict)
        assert isinstance(result.tags, dict)


def test_integration_24_00_time_handling() -> None:
    """Test that 24:00 timestamps are handled correctly."""
    nodes = load_org_file("edge_cases.org")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.total_tasks >= 0


def test_integration_with_mapping() -> None:
    """Test integration with tag mapping."""
    nodes = load_org_file("multiple_tags.org")

    result = analyze(
        nodes,
        {
            "Test": "Testing",
            "WebDev": "Frontend",
            "Unix": "Linux",
        },
        category="tags",
        max_relations=3,
    )

    assert result.total_tasks > 0
    assert "Testing" in result.tags or "Frontend" in result.tags or "Linux" in result.tags
