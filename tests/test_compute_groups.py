"""Tests for the compute_groups() function."""

from datetime import date, datetime

from orgstats.analyze import Frequency, Relations, Tag, TimeRange, compute_groups


def make_tag(name: str, relations_dict: dict[str, int], time_range: TimeRange | None = None) -> Tag:
    """Helper to create a Tag with specified relations."""
    return Tag(
        name=name,
        frequency=Frequency(0),
        relations=Relations(name=name, relations=relations_dict),
        time_range=time_range or TimeRange(),
        total_tasks=0,
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
    )


def test_compute_groups_empty_relations() -> None:
    """Test compute_groups with empty tags dictionary."""
    tags: dict[str, Tag] = {}
    groups = compute_groups(tags, max_relations=3)

    assert groups == []


def test_compute_groups_single_tag() -> None:
    """Test compute_groups with a single tag with no relations."""
    tags = {
        "python": make_tag("python", {}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 1
    assert groups[0].tags == ["python"]


def test_compute_groups_two_separate_tags() -> None:
    """Test two tags with no relations between them."""
    tags = {
        "python": make_tag("python", {}),
        "java": make_tag("java", {}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"python"} in tag_sets
    assert {"java"} in tag_sets


def test_compute_groups_bidirectional_pair() -> None:
    """Test two tags with mutual relations form a single group."""
    tags = {
        "python": make_tag("python", {"testing": 5}),
        "testing": make_tag("testing", {"python": 5}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 1
    assert set(groups[0].tags) == {"python", "testing"}
    assert groups[0].tags == ["python", "testing"]


def test_compute_groups_alphabetical_sorting() -> None:
    """Test that tags within a group are sorted alphabetically."""
    tags = {
        "zebra": make_tag("zebra", {"apple": 5, "banana": 3}),
        "apple": make_tag("apple", {"zebra": 5, "banana": 2}),
        "banana": make_tag("banana", {"zebra": 3, "apple": 2}),
    }
    groups = compute_groups(tags, max_relations=5)

    assert len(groups) == 1
    assert groups[0].tags == ["apple", "banana", "zebra"]


def test_compute_groups_respects_max_relations() -> None:
    """Test that only top max_relations are considered."""
    tags = {
        "python": make_tag("python", {"a": 10, "b": 8, "c": 6, "d": 4, "e": 2}),
        "a": make_tag("a", {"python": 10}),
        "b": make_tag("b", {"python": 8}),
        "c": make_tag("c", {"python": 6}),
        "d": make_tag("d", {"python": 4}),
        "e": make_tag("e", {"python": 2}),
    }
    groups = compute_groups(tags, max_relations=2)

    group_with_python = next(g for g in groups if "python" in g.tags)
    assert set(group_with_python.tags) == {"a", "b", "python"}


def test_compute_groups_multiple_components() -> None:
    """Test multiple separate strongly connected components."""
    tags = {
        "python": make_tag("python", {"testing": 5}),
        "testing": make_tag("testing", {"python": 5}),
        "java": make_tag("java", {"debugging": 3}),
        "debugging": make_tag("debugging", {"java": 3}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"python", "testing"} in tag_sets
    assert {"debugging", "java"} in tag_sets


def test_compute_groups_chain_within_limit() -> None:
    """Test a chain of relations A->B->C with max_relations=1."""
    tags = {
        "a": make_tag("a", {"b": 5}),
        "b": make_tag("b", {"c": 5}),
        "c": make_tag("c", {}),
    }
    groups = compute_groups(tags, max_relations=1)

    assert len(groups) == 3
    tag_sets = [set(group.tags) for group in groups]
    assert {"a"} in tag_sets
    assert {"b"} in tag_sets
    assert {"c"} in tag_sets


def test_compute_groups_complex_cycle() -> None:
    """Test a complex cycle: A->B->C->A."""
    tags = {
        "a": make_tag("a", {"b": 10}),
        "b": make_tag("b", {"c": 10}),
        "c": make_tag("c", {"a": 10}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 1
    assert set(groups[0].tags) == {"a", "b", "c"}


def test_compute_groups_multiple_cycles() -> None:
    """Test multiple separate cycles."""
    tags = {
        "a": make_tag("a", {"b": 10}),
        "b": make_tag("b", {"c": 10}),
        "c": make_tag("c", {"a": 10}),
        "x": make_tag("x", {"y": 5}),
        "y": make_tag("y", {"z": 5}),
        "z": make_tag("z", {"x": 5}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"a", "b", "c"} in tag_sets
    assert {"x", "y", "z"} in tag_sets


def test_compute_groups_asymmetric_relations() -> None:
    """Test asymmetric relations: A->B but B does not point to A."""
    tags = {
        "a": make_tag("a", {"b": 10}),
        "b": make_tag("b", {}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 2
    tag_sets = [set(group.tags) for group in groups]
    assert {"a"} in tag_sets
    assert {"b"} in tag_sets


def test_compute_groups_partial_cycle() -> None:
    """Test partial cycle: A->B->C, C->A, but B doesn't point back."""
    tags = {
        "a": make_tag("a", {"b": 10}),
        "b": make_tag("b", {"c": 10}),
        "c": make_tag("c", {"a": 10}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 1
    assert set(groups[0].tags) == {"a", "b", "c"}


def test_compute_groups_mixed_components() -> None:
    """Test mix of isolated tags, pairs, and larger components."""
    tags = {
        "isolated": make_tag("isolated", {}),
        "pair1": make_tag("pair1", {"pair2": 5}),
        "pair2": make_tag("pair2", {"pair1": 5}),
        "cycle1": make_tag("cycle1", {"cycle2": 10}),
        "cycle2": make_tag("cycle2", {"cycle3": 10}),
        "cycle3": make_tag("cycle3", {"cycle1": 10}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 3
    tag_sets = [set(group.tags) for group in groups]
    assert {"isolated"} in tag_sets
    assert {"pair1", "pair2"} in tag_sets
    assert {"cycle1", "cycle2", "cycle3"} in tag_sets


def test_compute_groups_real_world_scenario() -> None:
    """Test a realistic scenario with mixed relations."""
    tags = {
        "python": make_tag("python", {"testing": 10, "debugging": 5}),
        "testing": make_tag("testing", {"python": 10, "pytest": 8}),
        "pytest": make_tag("pytest", {"testing": 8}),
        "debugging": make_tag("debugging", {"python": 5}),
        "java": make_tag("java", {"maven": 7}),
        "maven": make_tag("maven", {"java": 7}),
    }
    groups = compute_groups(tags, max_relations=3)

    tag_sets = [set(group.tags) for group in groups]
    assert {"python", "testing"} <= tag_sets[0] or {"python", "testing"} <= tag_sets[1]
    assert {"java", "maven"} in tag_sets


def test_compute_groups_single_direction_chain() -> None:
    """Test a single-direction chain: A->B->C->D."""
    tags = {
        "a": make_tag("a", {"b": 10}),
        "b": make_tag("b", {"c": 10}),
        "c": make_tag("c", {"d": 10}),
        "d": make_tag("d", {}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 4
    tag_sets = [set(group.tags) for group in groups]
    assert {"a"} in tag_sets
    assert {"b"} in tag_sets
    assert {"c"} in tag_sets
    assert {"d"} in tag_sets


def test_compute_groups_with_time_ranges() -> None:
    """Test that groups receive combined time ranges."""
    python_time_range = TimeRange(
        earliest=datetime(2023, 1, 1),
        latest=datetime(2023, 1, 5),
        timeline={date(2023, 1, 1): 3, date(2023, 1, 5): 2},
    )
    testing_time_range = TimeRange(
        earliest=datetime(2023, 1, 3),
        latest=datetime(2023, 1, 7),
        timeline={date(2023, 1, 3): 4, date(2023, 1, 7): 1},
    )

    tags = {
        "python": make_tag("python", {"testing": 5}, python_time_range),
        "testing": make_tag("testing", {"python": 5}, testing_time_range),
    }
    groups = compute_groups(tags, max_relations=3)

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
    python_time_range = TimeRange(
        earliest=datetime(2023, 1, 1),
        latest=datetime(2023, 1, 5),
        timeline={date(2023, 1, 1): 3, date(2023, 1, 3): 2, date(2023, 1, 5): 1},
    )
    testing_time_range = TimeRange(
        earliest=datetime(2023, 1, 3),
        latest=datetime(2023, 1, 7),
        timeline={date(2023, 1, 3): 4, date(2023, 1, 5): 2, date(2023, 1, 7): 1},
    )

    tags = {
        "python": make_tag("python", {"testing": 5}, python_time_range),
        "testing": make_tag("testing", {"python": 5}, testing_time_range),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 1
    assert groups[0].time_range.timeline == {
        date(2023, 1, 1): 3,
        date(2023, 1, 3): 6,
        date(2023, 1, 5): 3,
        date(2023, 1, 7): 1,
    }


def test_compute_groups_time_range_empty_when_no_data() -> None:
    """Test that groups with no time range data get empty TimeRange."""
    tags = {
        "python": make_tag("python", {"testing": 5}),
        "testing": make_tag("testing", {"python": 5}),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 1
    assert groups[0].time_range.earliest is None
    assert groups[0].time_range.latest is None
    assert groups[0].time_range.timeline == {}


def test_compute_groups_multiple_groups_separate_time_ranges() -> None:
    """Test that multiple groups have independent time ranges."""
    python_time_range = TimeRange(
        earliest=datetime(2023, 1, 1),
        latest=datetime(2023, 1, 5),
        timeline={date(2023, 1, 1): 3},
    )
    testing_time_range = TimeRange(
        earliest=datetime(2023, 1, 3),
        latest=datetime(2023, 1, 7),
        timeline={date(2023, 1, 3): 4},
    )
    java_time_range = TimeRange(
        earliest=datetime(2023, 6, 1),
        latest=datetime(2023, 6, 10),
        timeline={date(2023, 6, 1): 5},
    )
    maven_time_range = TimeRange(
        earliest=datetime(2023, 6, 5),
        latest=datetime(2023, 6, 15),
        timeline={date(2023, 6, 5): 2},
    )

    tags = {
        "python": make_tag("python", {"testing": 5}, python_time_range),
        "testing": make_tag("testing", {"python": 5}, testing_time_range),
        "java": make_tag("java", {"maven": 3}, java_time_range),
        "maven": make_tag("maven", {"java": 3}, maven_time_range),
    }
    groups = compute_groups(tags, max_relations=3)

    assert len(groups) == 2

    python_group = next(g for g in groups if "python" in g.tags)
    assert python_group.time_range.earliest == datetime(2023, 1, 1)
    assert python_group.time_range.latest == datetime(2023, 1, 7)

    java_group = next(g for g in groups if "java" in g.tags)
    assert java_group.time_range.earliest == datetime(2023, 6, 1)
    assert java_group.time_range.latest == datetime(2023, 6, 15)
