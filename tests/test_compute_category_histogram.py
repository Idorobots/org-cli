"""Tests for the compute_category_histogram() function."""

from orgstats.analyze import compute_category_histogram
from tests.conftest import node_from_org


def test_compute_category_histogram_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values.get("regular", 0) == 0
    assert histogram.values.get("hard", 0) == 0


def test_compute_category_histogram_single_simple() -> None:
    """Test single simple task (gamify_exp < 10)."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["simple"] == 1
    assert histogram.values.get("regular", 0) == 0
    assert histogram.values.get("hard", 0) == 0


def test_compute_category_histogram_single_regular() -> None:
    """Test single regular task (10 <= gamify_exp < 20)."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 15
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values["regular"] == 1
    assert histogram.values.get("hard", 0) == 0


def test_compute_category_histogram_single_hard() -> None:
    """Test single hard task (gamify_exp >= 20)."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values.get("regular", 0) == 0
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_missing_gamify_exp_defaults_regular() -> None:
    """Test task without gamify_exp defaults to regular."""
    nodes = node_from_org("* DONE Task\n")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values["regular"] == 1
    assert histogram.values.get("hard", 0) == 0


def test_compute_category_histogram_multiple_tasks() -> None:
    """Test multiple tasks across categories."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 15
:END:

* DONE Task 3
:PROPERTIES:
:gamify_exp: 25
:END:

* DONE Task 4
:PROPERTIES:
:gamify_exp: 8
:END:

* DONE Task 5
:PROPERTIES:
:gamify_exp: 12
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["simple"] == 2
    assert histogram.values["regular"] == 2
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_boundary_values() -> None:
    """Test boundary values for categories."""
    nodes = node_from_org("""
* DONE Task at 9
:PROPERTIES:
:gamify_exp: 9
:END:

* DONE Task at 10
:PROPERTIES:
:gamify_exp: 10
:END:

* DONE Task at 19
:PROPERTIES:
:gamify_exp: 19
:END:

* DONE Task at 20
:PROPERTIES:
:gamify_exp: 20
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["simple"] == 1
    assert histogram.values["regular"] == 2
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_repeated_tasks() -> None:
    """Test repeated tasks count individually."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 15
:END:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["regular"] == 2


def test_compute_category_histogram_todo_tasks_excluded() -> None:
    """Test that TODO tasks are not counted."""
    nodes = node_from_org("""
* TODO Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 15
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values["regular"] == 1
    assert histogram.values.get("hard", 0) == 0


def test_compute_category_histogram_multiple_done_keys() -> None:
    """Test with multiple done keys."""
    import orgparse

    content = """#+TODO: TODO | DONE COMPLETED

* DONE Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* COMPLETED Task 2
:PROPERTIES:
:gamify_exp: 25
:END:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    histogram = compute_category_histogram(nodes, ["DONE", "COMPLETED"])

    assert histogram.values["simple"] == 1
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_cancelled_tasks_excluded() -> None:
    """Test that CANCELLED tasks are not counted."""
    import orgparse

    content = """#+TODO: TODO | DONE CANCELLED

* CANCELLED Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 15
:END:
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values["regular"] == 1


def test_compute_category_histogram_tuple_format() -> None:
    """Test gamify_exp in tuple format (X Y)."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:gamify_exp: (5 10)
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: (25 30)
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["simple"] == 1
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_mixed_formats() -> None:
    """Test mixture of integer and tuple formats."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:gamify_exp: 8
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: (15 20)
:END:

* DONE Task 3

* DONE Task 4
:PROPERTIES:
:gamify_exp: (22 25)
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["simple"] == 1
    assert histogram.values["regular"] == 2
    assert histogram.values["hard"] == 1


def test_compute_category_histogram_zero_value() -> None:
    """Test gamify_exp of 0 is simple."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 0
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["simple"] == 1


def test_compute_category_histogram_large_value() -> None:
    """Test large gamify_exp value is hard."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: 100
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values["hard"] == 1


def test_compute_category_histogram_sum_equals_done_count() -> None:
    """Test that sum of category counts equals total DONE tasks."""
    nodes = node_from_org("""
* TODO Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 8
:END:

* DONE Task 3
:PROPERTIES:
:gamify_exp: 15
:END:

* DONE Task 4
:PROPERTIES:
:gamify_exp: 25
:END:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    total_category_counts = sum(histogram.values.values())
    assert total_category_counts == 4


def test_compute_category_histogram_invalid_gamify_exp() -> None:
    """Test invalid gamify_exp defaults to regular."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp: invalid
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values["regular"] == 1
    assert histogram.values.get("hard", 0) == 0


def test_compute_category_histogram_empty_gamify_exp() -> None:
    """Test empty gamify_exp defaults to regular."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:gamify_exp:
:END:
""")

    histogram = compute_category_histogram(nodes, ["DONE"])

    assert histogram.values.get("simple", 0) == 0
    assert histogram.values["regular"] == 1
    assert histogram.values.get("hard", 0) == 0
