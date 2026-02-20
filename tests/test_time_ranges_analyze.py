"""Tests for time range computation in analyze()."""

from datetime import date

import orgparse

from orgstats.analyze import analyze
from tests.conftest import node_from_org


def test_analyze_empty_nodes_empty_time_ranges() -> None:
    """Test empty nodes returns empty time ranges."""
    nodes: list[orgparse.node.OrgNode] = []
    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tags == {}


def test_analyze_single_task_time_range() -> None:
    """Test single task creates TimeRange."""
    nodes = node_from_org("""
* DONE Test :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "Python" in result.tags
    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 20
    assert tr.earliest is not None
    assert tr.earliest.hour == 14 and tr.earliest.minute == 43
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 20


def test_analyze_multiple_tasks_time_range() -> None:
    """Test multiple tasks update TimeRange correctly."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-18 Wed 09:15]
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 18
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 20


def test_analyze_time_range_with_repeated_tasks() -> None:
    """Test repeated tasks update TimeRange."""
    nodes = node_from_org("""
* TODO Task :Daily:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Daily"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 18
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 19


def test_analyze_time_range_fallback_to_closed() -> None:
    """Test fallback to closed timestamp."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 20
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 20


def test_analyze_time_range_fallback_to_scheduled() -> None:
    """Test fallback to scheduled timestamp for DONE tasks."""
    nodes = node_from_org("""
* DONE Task :Python:
SCHEDULED: <2023-10-20 Fri>
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 20
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 20


def test_analyze_time_range_fallback_to_deadline() -> None:
    """Test fallback to deadline timestamp for DONE tasks."""
    nodes = node_from_org("""
* DONE Task :Python:
DEADLINE: <2023-10-25 Wed>
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 25
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 25


def test_analyze_time_range_no_timestamps_counted() -> None:
    """Test tasks without timestamps are counted but have empty time ranges."""
    nodes = node_from_org("* TODO Task :Python:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "Python" in result.tags
    assert result.tags["Python"].total_tasks == 1
    assert result.tags["Python"].time_range.earliest is None
    assert result.tags["Python"].time_range.latest is None


def test_analyze_time_range_normalized_tags() -> None:
    """Test time ranges use normalized tags."""
    nodes = node_from_org("""
* DONE Task :Test:SysAdmin:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(
        nodes,
        {"Test": "Testing", "SysAdmin": "DevOps"},
        category="tags",
        max_relations=3,
    )

    assert "Testing" in result.tags
    assert "DevOps" in result.tags


def test_analyze_time_range_heading_separate() -> None:
    """Test heading time ranges computed for heading category."""
    nodes = node_from_org("""
* DONE Implement feature
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="heading", max_relations=3)

    assert "implement" in result.tags
    assert "feature" in result.tags


def test_analyze_time_range_body_separate() -> None:
    """Test body time ranges computed for body category."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-20 Fri 14:43]
Python code
""")

    result = analyze(nodes, {}, category="body", max_relations=3)

    assert "python" in result.tags
    assert "code" in result.tags


def test_analyze_time_range_earliest_latest() -> None:
    """Test earliest and latest are correctly tracked."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-19 Thu 10:00]
* DONE Task :Python:
CLOSED: [2023-10-18 Wed 09:15]
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 18
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 20


def test_analyze_time_range_same_timestamp() -> None:
    """Test multiple tasks with same timestamp."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Python"].time_range
    assert tr.earliest is not None
    assert tr.earliest.year == 2023 and tr.earliest.month == 10 and tr.earliest.day == 20
    assert tr.latest is not None
    assert tr.latest.year == 2023 and tr.latest.month == 10 and tr.latest.day == 20


def test_analyze_result_has_time_range_fields() -> None:
    """Test AnalysisResult includes time range fields."""
    from orgstats.analyze import AnalysisResult

    nodes: list[orgparse.node.OrgNode] = []
    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert isinstance(result, AnalysisResult)
    assert result.tags == {}


def test_analyze_time_range_multiple_tags() -> None:
    """Test multiple tags in single task update separately."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    python_tr = result.tags["Python"].time_range
    assert python_tr.earliest is not None
    assert python_tr.earliest.day == 20
    testing_tr = result.tags["Testing"].time_range
    assert testing_tr.earliest is not None
    assert testing_tr.earliest.day == 20


def test_analyze_time_range_repeated_all_done() -> None:
    """Test all DONE repeated tasks contribute to time range."""
    nodes = node_from_org("""
* TODO Task :Daily:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    tr = result.tags["Daily"].time_range
    assert tr.earliest is not None
    assert tr.earliest.day == 18
    assert tr.latest is not None
    assert tr.latest.day == 20


def test_analyze_timeline_single_task() -> None:
    """Test single task creates timeline with one entry."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "Python" in result.tags
    timeline = result.tags["Python"].time_range.timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_analyze_timeline_multiple_tasks_different_days() -> None:
    """Test multiple tasks on different days create multiple timeline entries."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-18 Wed 09:15]
* DONE Task :Python:
CLOSED: [2023-10-19 Thu 10:00]
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    timeline = result.tags["Python"].time_range.timeline
    assert len(timeline) == 3
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_analyze_timeline_multiple_tasks_same_day() -> None:
    """Test multiple tasks on same day increment same timeline entry."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 09:15]
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    timeline = result.tags["Python"].time_range.timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 2


def test_analyze_timeline_repeated_tasks() -> None:
    """Test repeated tasks all appear in timeline."""
    nodes = node_from_org("""
* TODO Task :Daily:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    timeline = result.tags["Daily"].time_range.timeline
    assert len(timeline) == 3
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_analyze_timeline_repeated_tasks_same_day() -> None:
    """Test repeated tasks on same day increment counter."""
    nodes = node_from_org("""
* TODO Task :Daily:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:30]
- State "DONE"       from "TODO"       [2023-10-20 Fri 18:00]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    timeline = result.tags["Daily"].time_range.timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 3


def test_analyze_timeline_mixed_repeats_and_regular() -> None:
    """Test mix of repeated and regular tasks."""
    nodes = node_from_org("""
* TODO Task :Python:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
:END:
* DONE Task :Python:
CLOSED: [2023-10-19 Thu 15:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    timeline = result.tags["Python"].time_range.timeline
    assert len(timeline) == 2
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 2
