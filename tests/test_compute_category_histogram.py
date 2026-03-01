"""Tests for the compute_category_histogram() function."""

from org.analyze import compute_category_histogram
from tests.conftest import node_from_org


def test_compute_category_histogram_empty_nodes() -> None:
    """Empty input should produce an empty histogram."""
    histogram = compute_category_histogram([], "CATEGORY")
    assert histogram.values == {}


def test_compute_category_histogram_counts_category_values() -> None:
    """Histogram should count explicit category property values."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY: hard
:END:

* DONE Task 3
:PROPERTIES:
:CATEGORY: simple
:END:
""")

    histogram = compute_category_histogram(nodes, "CATEGORY")

    assert histogram.values["simple"] == 2
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_uses_none_for_missing_category() -> None:
    """Missing category property should be recorded as none."""
    nodes = node_from_org("* DONE Task\n")

    histogram = compute_category_histogram(nodes, "CATEGORY")

    assert histogram.values["none"] == 1


def test_compute_category_histogram_uses_none_for_empty_category() -> None:
    """Empty category property should be recorded as none."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:CATEGORY:
:END:
""")

    histogram = compute_category_histogram(nodes, "CATEGORY")

    assert histogram.values["none"] == 1


def test_compute_category_histogram_supports_custom_property_name() -> None:
    """Histogram should read categories from a custom property key."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:TASK_TYPE: alpha
:END:

* DONE Task 2
:PROPERTIES:
:TASK_TYPE: beta
:END:
""")

    histogram = compute_category_histogram(nodes, "TASK_TYPE")

    assert histogram.values["alpha"] == 1
    assert histogram.values["beta"] == 1


def test_compute_category_histogram_counts_repeats() -> None:
    """Repeated tasks should contribute repeat count to category totals."""
    nodes = node_from_org("""
* DONE Repeated
:PROPERTIES:
:CATEGORY: simple
:END:
- State "DONE"       from "TODO"       [2024-01-02 Tue 10:00]
- State "DONE"       from "TODO"       [2024-01-03 Wed 10:00]
""")

    histogram = compute_category_histogram(nodes, "CATEGORY")

    assert histogram.values["simple"] == 2
