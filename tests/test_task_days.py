"""Tests for day-of-week task completion histogram."""

from datetime import datetime

import orgparse

from orgstats.analyze import analyze, weekday_to_string
from orgstats.histogram import Histogram
from tests.conftest import node_from_org


def test_weekday_to_string_all_days() -> None:
    """Test weekday_to_string maps all weekday integers correctly."""
    assert weekday_to_string(0) == "Monday"
    assert weekday_to_string(1) == "Tuesday"
    assert weekday_to_string(2) == "Wednesday"
    assert weekday_to_string(3) == "Thursday"
    assert weekday_to_string(4) == "Friday"
    assert weekday_to_string(5) == "Saturday"
    assert weekday_to_string(6) == "Sunday"


def test_weekday_to_string_with_datetime() -> None:
    """Test weekday_to_string works with datetime.weekday() output."""
    dt_monday = datetime(2023, 10, 23)
    dt_sunday = datetime(2023, 10, 29)

    assert weekday_to_string(dt_monday.weekday()) == "Monday"
    assert weekday_to_string(dt_sunday.weekday()) == "Sunday"


def test_single_done_task_with_closed_timestamp() -> None:
    """Test single DONE task appears on correct day."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-23 Mon 10:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("Monday", 0) == 1
    assert result.task_days.values.get("Tuesday", 0) == 0


def test_repeated_done_tasks_multiple_days() -> None:
    """Test multiple DONE repeats increment multiple days."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-23 Mon 14:43]
- State "DONE"       from "TODO"       [2023-10-24 Tue 10:00]
- State "DONE"       from "TODO"       [2023-10-25 Wed 09:15]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1
    assert result.task_days.values["Tuesday"] == 1
    assert result.task_days.values["Wednesday"] == 1
    assert result.task_days.values.get("Thursday", 0) == 0


def test_repeated_done_tasks_same_day() -> None:
    """Test multiple DONE repeats on same day increment that day multiple times."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-23 Mon 14:43]
- State "DONE"       from "TODO"       [2023-10-23 Mon 10:00]
- State "DONE"       from "TODO"       [2023-10-23 Mon 09:15]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 3
    assert result.task_days.values.get("Tuesday", 0) == 0


def test_todo_task_not_counted() -> None:
    """Test TODO tasks don't appear in histogram."""
    nodes = node_from_org("""
* TODO Task
SCHEDULED: <2023-10-23 Mon>
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("Monday", 0) == 0
    assert result.task_days.values == {}


def test_mixed_repeated_tasks_only_done_counted() -> None:
    """Test only DONE repeats counted, not TODO repeats."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-23 Mon 14:43]
- State "TODO"       from "DONE"       [2023-10-24 Tue 10:00]
- State "DONE"       from "TODO"       [2023-10-25 Wed 09:15]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1
    assert result.task_days.values.get("Tuesday", 0) == 0
    assert result.task_days.values["Wednesday"] == 1


def test_done_task_without_timestamp() -> None:
    """Test DONE task with no timestamp is counted as 'unknown'."""
    nodes = node_from_org("""
* DONE Task
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("unknown", 0) == 1


def test_all_days_different_weekdays() -> None:
    """Test tasks on all 7 days populate all 7 entries."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-23 Mon 10:00]

* DONE Task 2
CLOSED: [2023-10-24 Tue 10:00]

* DONE Task 3
CLOSED: [2023-10-25 Wed 10:00]

* DONE Task 4
CLOSED: [2023-10-26 Thu 10:00]

* DONE Task 5
CLOSED: [2023-10-27 Fri 10:00]

* DONE Task 6
CLOSED: [2023-10-28 Sat 10:00]

* DONE Task 7
CLOSED: [2023-10-29 Sun 10:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1
    assert result.task_days.values["Tuesday"] == 1
    assert result.task_days.values["Wednesday"] == 1
    assert result.task_days.values["Thursday"] == 1
    assert result.task_days.values["Friday"] == 1
    assert result.task_days.values["Saturday"] == 1
    assert result.task_days.values["Sunday"] == 1


def test_task_days_in_analyze_result() -> None:
    """Test task_days field exists and is populated correctly."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-23 Mon 10:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert isinstance(result.task_days, Histogram)
    assert result.task_days.values["Monday"] == 1


def test_empty_nodes_task_days() -> None:
    """Test empty nodes list produces empty histogram."""
    nodes: list[orgparse.node.OrgNode] = []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values == {}


def test_cancelled_task_not_counted() -> None:
    """Test CANCELLED task is not counted in day histogram."""
    content = """#+TODO: TODO | DONE CANCELLED

* CANCELLED Task
CLOSED: [2023-10-23 Mon 10:00]
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("Monday", 0) == 0
    assert result.task_days.values == {}


def test_suspended_task_not_counted() -> None:
    """Test SUSPENDED task is not counted in day histogram."""
    content = """#+TODO: TODO | DONE SUSPENDED

* SUSPENDED Task
CLOSED: [2023-10-23 Mon 10:00]
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("Monday", 0) == 0
    assert result.task_days.values == {}


def test_done_task_with_scheduled_timestamp() -> None:
    """Test DONE task uses scheduled timestamp when no closed timestamp."""
    nodes = node_from_org("""
* DONE Task
SCHEDULED: <2023-10-23 Mon>
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1


def test_done_task_with_deadline_timestamp() -> None:
    """Test DONE task uses deadline timestamp when no closed or scheduled."""
    nodes = node_from_org("""
* DONE Task
DEADLINE: <2023-10-23 Mon>
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1


def test_repeated_tasks_priority_over_closed() -> None:
    """Test repeated DONE tasks take priority over closed timestamp."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-24 Tue 10:00]
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-23 Mon 14:43]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1
    assert result.task_days.values.get("Tuesday", 0) == 0


def test_multiple_tasks_accumulate_same_day() -> None:
    """Test multiple separate DONE tasks on same day accumulate."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-23 Mon 10:00]

* DONE Task 2
CLOSED: [2023-10-23 Mon 14:00]

* DONE Task 3
CLOSED: [2023-10-23 Mon 18:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 3


def test_main_done_and_repeated_done_both_counted() -> None:
    """Test main DONE node and repeated DONE tasks both contribute."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-23 Mon 10:00]
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-23 Mon 14:43]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1


def test_task_days_independent_of_category() -> None:
    """Test task_days histogram is same regardless of category analyzed."""
    nodes = node_from_org("""
* DONE Task :Tag:
CLOSED: [2023-10-23 Mon 10:00]
""")

    result_tags = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])
    result_heading = analyze(nodes, {}, category="heading", max_relations=3, done_keys=["DONE"])
    result_body = analyze(nodes, {}, category="body", max_relations=3, done_keys=["DONE"])

    assert result_tags.task_days.values == result_heading.task_days.values
    assert result_heading.task_days.values == result_body.task_days.values
    assert result_tags.task_days.values["Monday"] == 1


def test_done_task_with_datelist_timestamp() -> None:
    """Test DONE task with datelist timestamp (timestamp in body)."""
    nodes = node_from_org("""
* DONE Task
[2023-10-23 Mon 14:30]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1


def test_done_task_with_multiple_datelist_timestamps() -> None:
    """Test DONE task with multiple datelist timestamps."""
    nodes = node_from_org("""
* DONE Task
[2023-10-23 Mon 14:30]
[2023-10-24 Tue 10:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1
    assert result.task_days.values["Tuesday"] == 1


def test_done_task_without_any_timestamp_unknown() -> None:
    """Test DONE task with no timestamp increments 'unknown'."""
    nodes = node_from_org("""
* DONE Task
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("unknown", 0) == 1
    assert result.task_days.values.get("Monday", 0) == 0


def test_multiple_done_tasks_without_timestamp() -> None:
    """Test multiple DONE tasks without timestamps accumulate 'unknown'."""
    nodes = node_from_org("""
* DONE Task 1

* DONE Task 2

* DONE Task 3
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["unknown"] == 3


def test_done_with_and_without_timestamps_mixed() -> None:
    """Test mix of tasks with and without timestamps."""
    nodes = node_from_org("""
* DONE Task with timestamp
CLOSED: [2023-10-23 Mon 10:00]

* DONE Task without timestamp

* DONE Another with timestamp
CLOSED: [2023-10-24 Tue 14:00]

* DONE Another without timestamp
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values["Monday"] == 1
    assert result.task_days.values["Tuesday"] == 1
    assert result.task_days.values["unknown"] == 2


def test_unknown_not_shown_for_tasks_with_timestamps() -> None:
    """Test 'unknown' is not present when all tasks have timestamps."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-23 Mon 10:00]

* DONE Task 2
CLOSED: [2023-10-24 Tue 14:00]
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("unknown", 0) == 0
    assert "unknown" not in result.task_days.values


def test_unknown_matches_missing_done_count() -> None:
    """Test DONE count equals sum of days plus unknown."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-23 Mon 10:00]

* DONE Task 2

* DONE Task 3
CLOSED: [2023-10-24 Tue 14:00]

* DONE Task 4

* TODO Not counted
SCHEDULED: <2023-10-25 Wed>
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    done_count = result.task_states.values.get("DONE", 0)
    day_sum = sum(
        result.task_days.values.get(day, 0)
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    )
    unknown_count = result.task_days.values.get("unknown", 0)

    assert done_count == day_sum + unknown_count
    assert done_count == 4
    assert day_sum == 2
    assert unknown_count == 2


def test_todo_task_without_timestamp_not_counted() -> None:
    """Test TODO tasks without timestamps are not counted in unknown."""
    nodes = node_from_org("""
* TODO Task 1

* TODO Task 2
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("unknown", 0) == 0
    assert result.task_days.values == {}


def test_cancelled_task_without_timestamp_not_counted() -> None:
    """Test CANCELLED tasks without timestamps are not counted in unknown."""
    content = """#+TODO: TODO | DONE CANCELLED

* CANCELLED Task
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])

    assert result.task_days.values.get("unknown", 0) == 0
    assert result.task_days.values == {}
