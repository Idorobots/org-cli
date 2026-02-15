"""Tests for the compute_groups() function."""

from datetime import date, datetime

from orgstats.core import Relations, TimeRange, compute_groups


def test_compute_groups_empty_relations() -> None:
    """Test compute_groups with empty relations dictionary."""
    relations: dict[str, Relations] = {}
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert groups == []


def test_compute_groups_single_tag() -> None:
    """Test compute_groups with a single tag with no relations."""
    relations = {
        "python": Relations(name="python", relations={}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 1
    assert groups[0].tags == ["python"]


def test_compute_groups_two_separate_tags() -> None:
    """Test two tags with no relations between them."""
    relations = {
        "python": Relations(name="python", relations={}),
        "java": Relations(name="java", relations={}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"python"} in tag_sets
    assert {"java"} in tag_sets


def test_compute_groups_bidirectional_pair() -> None:
    """Test two tags with mutual relations form a single group."""
    relations = {
        "python": Relations(name="python", relations={"testing": 5}),
        "testing": Relations(name="testing", relations={"python": 5}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 1
    assert set(groups[0].tags) == {"python", "testing"}
    assert groups[0].tags == ["python", "testing"]


def test_compute_groups_alphabetical_sorting() -> None:
    """Test that tags within a group are sorted alphabetically."""
    relations = {
        "zebra": Relations(name="zebra", relations={"apple": 5, "banana": 3}),
        "apple": Relations(name="apple", relations={"zebra": 5, "banana": 2}),
        "banana": Relations(name="banana", relations={"zebra": 3, "apple": 2}),
    }
    groups = compute_groups(relations, max_relations=5, tag_time_ranges={})

    assert len(groups) == 1
    assert groups[0].tags == ["apple", "banana", "zebra"]


def test_compute_groups_respects_max_relations() -> None:
    """Test that only top max_relations are considered."""
    relations = {
        "python": Relations(name="python", relations={"a": 10, "b": 8, "c": 6, "d": 4, "e": 2}),
        "a": Relations(name="a", relations={"python": 10}),
        "b": Relations(name="b", relations={"python": 8}),
        "c": Relations(name="c", relations={"python": 6}),
        "d": Relations(name="d", relations={"python": 4}),
        "e": Relations(name="e", relations={"python": 2}),
    }
    groups = compute_groups(relations, max_relations=2, tag_time_ranges={})

    group_with_python = next(g for g in groups if "python" in g.tags)
    assert set(group_with_python.tags) == {"a", "b", "python"}


def test_compute_groups_multiple_components() -> None:
    """Test multiple separate strongly connected components."""
    relations = {
        "python": Relations(name="python", relations={"testing": 5}),
        "testing": Relations(name="testing", relations={"python": 5}),
        "java": Relations(name="java", relations={"debugging": 3}),
        "debugging": Relations(name="debugging", relations={"java": 3}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"python", "testing"} in tag_sets
    assert {"debugging", "java"} in tag_sets


def test_compute_groups_chain_within_limit() -> None:
    """Test a chain of relations A->B->C with max_relations=1."""
    relations = {
        "a": Relations(name="a", relations={"b": 5}),
        "b": Relations(name="b", relations={"c": 5}),
        "c": Relations(name="c", relations={}),
    }
    groups = compute_groups(relations, max_relations=1, tag_time_ranges={})

    assert len(groups) == 3
    tag_sets = [set(group.tags) for group in groups]
    assert {"a"} in tag_sets
    assert {"b"} in tag_sets
    assert {"c"} in tag_sets


def test_compute_groups_complex_cycle() -> None:
    """Test a complex cycle: A->B->C->A."""
    relations = {
        "a": Relations(name="a", relations={"b": 10}),
        "b": Relations(name="b", relations={"c": 10}),
        "c": Relations(name="c", relations={"a": 10}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 1
    assert set(groups[0].tags) == {"a", "b", "c"}


def test_compute_groups_multiple_cycles() -> None:
    """Test multiple separate cycles."""
    relations = {
        "a": Relations(name="a", relations={"b": 10}),
        "b": Relations(name="b", relations={"c": 10}),
        "c": Relations(name="c", relations={"a": 10}),
        "x": Relations(name="x", relations={"y": 5}),
        "y": Relations(name="y", relations={"z": 5}),
        "z": Relations(name="z", relations={"x": 5}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"a", "b", "c"} in tag_sets
    assert {"x", "y", "z"} in tag_sets


def test_compute_groups_asymmetric_relations() -> None:
    """Test asymmetric relations: A->B but B does not point to A."""
    relations = {
        "a": Relations(name="a", relations={"b": 10}),
        "b": Relations(name="b", relations={}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"a"} in tag_sets
    assert {"b"} in tag_sets


def test_compute_groups_partial_cycle() -> None:
    """Test partial cycle: A->B->C, C->A, but B doesn't point back."""
    relations = {
        "a": Relations(name="a", relations={"b": 10}),
        "b": Relations(name="b", relations={"c": 10}),
        "c": Relations(name="c", relations={"a": 10}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 1
    assert set(groups[0].tags) == {"a", "b", "c"}


def test_compute_groups_mixed_components() -> None:
    """Test mix of isolated tags, pairs, and larger components."""
    relations = {
        "isolated": Relations(name="isolated", relations={}),
        "pair1": Relations(name="pair1", relations={"pair2": 5}),
        "pair2": Relations(name="pair2", relations={"pair1": 5}),
        "cycle1": Relations(name="cycle1", relations={"cycle2": 10}),
        "cycle2": Relations(name="cycle2", relations={"cycle3": 10}),
        "cycle3": Relations(name="cycle3", relations={"cycle1": 10}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 3
    tag_sets = [set(group.tags) for group in groups]
    assert {"isolated"} in tag_sets
    assert {"pair1", "pair2"} in tag_sets
    assert {"cycle1", "cycle2", "cycle3"} in tag_sets


def test_compute_groups_real_world_scenario() -> None:
    """Test a realistic scenario with mixed relations."""
    relations = {
        "python": Relations(name="python", relations={"testing": 10, "debugging": 5}),
        "testing": Relations(name="testing", relations={"python": 10, "pytest": 8}),
        "pytest": Relations(name="pytest", relations={"testing": 8}),
        "debugging": Relations(name="debugging", relations={"python": 5}),
        "java": Relations(name="java", relations={"maven": 7}),
        "maven": Relations(name="maven", relations={"java": 7}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    tag_sets = [set(group.tags) for group in groups]
    assert {"python", "testing"} <= tag_sets[0] or {"python", "testing"} <= tag_sets[1]
    assert {"java", "maven"} in tag_sets


def test_compute_groups_single_direction_chain() -> None:
    """Test a single-direction chain: A->B->C->D."""
    relations = {
        "a": Relations(name="a", relations={"b": 10}),
        "b": Relations(name="b", relations={"c": 10}),
        "c": Relations(name="c", relations={"d": 10}),
        "d": Relations(name="d", relations={}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 4
    tag_sets = [set(group.tags) for group in groups]
    assert {"a"} in tag_sets
    assert {"b"} in tag_sets
    assert {"c"} in tag_sets
    assert {"d"} in tag_sets


def test_compute_groups_with_time_ranges() -> None:
    """Test that groups receive combined time ranges."""
    relations = {
        "python": Relations(name="python", relations={"testing": 5}),
        "testing": Relations(name="testing", relations={"python": 5}),
    }
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3, date(2023, 1, 5): 2},
        ),
        "testing": TimeRange(
            earliest=datetime(2023, 1, 3),
            latest=datetime(2023, 1, 7),
            timeline={date(2023, 1, 3): 4, date(2023, 1, 7): 1},
        ),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges=tag_time_ranges)

    assert len(groups) == 1
    assert groups[0].time_range.earliest == datetime(2023, 1, 1)
    assert groups[0].time_range.latest == datetime(2023, 1, 7)
    assert groups[0].time_range.timeline == {
        date(2023, 1, 1): 3,
        date(2023, 1, 3): 4,
        date(2023, 1, 5): 2,
        date(2023, 1, 7): 1,
    }


def test_compute_groups_time_range_combines_overlapping_dates() -> None:
    """Test that group time range merges and sums overlapping dates."""
    relations = {
        "python": Relations(name="python", relations={"testing": 5}),
        "testing": Relations(name="testing", relations={"python": 5}),
    }
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3, date(2023, 1, 3): 2, date(2023, 1, 5): 1},
        ),
        "testing": TimeRange(
            earliest=datetime(2023, 1, 3),
            latest=datetime(2023, 1, 7),
            timeline={date(2023, 1, 3): 4, date(2023, 1, 5): 2, date(2023, 1, 7): 1},
        ),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges=tag_time_ranges)

    assert len(groups) == 1
    assert groups[0].time_range.timeline == {
        date(2023, 1, 1): 3,
        date(2023, 1, 3): 6,
        date(2023, 1, 5): 3,
        date(2023, 1, 7): 1,
    }


def test_compute_groups_time_range_empty_when_no_data() -> None:
    """Test that groups with no time range data get empty TimeRange."""
    relations = {
        "python": Relations(name="python", relations={"testing": 5}),
        "testing": Relations(name="testing", relations={"python": 5}),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges={})

    assert len(groups) == 1
    assert groups[0].time_range.earliest is None
    assert groups[0].time_range.latest is None
    assert groups[0].time_range.timeline == {}


def test_compute_groups_multiple_groups_separate_time_ranges() -> None:
    """Test that multiple groups have independent time ranges."""
    relations = {
        "python": Relations(name="python", relations={"testing": 5}),
        "testing": Relations(name="testing", relations={"python": 5}),
        "java": Relations(name="java", relations={"maven": 3}),
        "maven": Relations(name="maven", relations={"java": 3}),
    }
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3},
        ),
        "testing": TimeRange(
            earliest=datetime(2023, 1, 3),
            latest=datetime(2023, 1, 7),
            timeline={date(2023, 1, 3): 4},
        ),
        "java": TimeRange(
            earliest=datetime(2023, 6, 1),
            latest=datetime(2023, 6, 10),
            timeline={date(2023, 6, 1): 5},
        ),
        "maven": TimeRange(
            earliest=datetime(2023, 6, 5),
            latest=datetime(2023, 6, 15),
            timeline={date(2023, 6, 5): 2},
        ),
    }
    groups = compute_groups(relations, max_relations=3, tag_time_ranges=tag_time_ranges)

    assert len(groups) == 2

    python_group = next(g for g in groups if "python" in g.tags)
    assert python_group.time_range.earliest == datetime(2023, 1, 1)
    assert python_group.time_range.latest == datetime(2023, 1, 7)

    java_group = next(g for g in groups if "java" in g.tags)
    assert java_group.time_range.earliest == datetime(2023, 6, 1)
    assert java_group.time_range.latest == datetime(2023, 6, 15)
