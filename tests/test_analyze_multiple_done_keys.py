"""Integration tests for analyze() with multiple done_keys."""

from datetime import datetime

from orgstats.analyze import analyze
from tests.conftest import node_from_org


def test_analyze_with_multiple_done_keys_basic() -> None:
    """Test analyze with multiple done states."""
    nodes = node_from_org(
        """
* DONE Task 1 :python:
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task 2 :python:
CLOSED: [2023-10-19 Thu 10:00]

* ARCHIVED Task 3 :python:
CLOSED: [2023-10-20 Fri 14:43]

* TODO Task 4 :python:
CLOSED: [2023-10-25 Wed 12:00]
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.total_tasks == 4
    assert result.task_states.values["DONE"] == 1
    assert result.task_states.values["CANCELLED"] == 1
    assert result.task_states.values["ARCHIVED"] == 1
    assert result.task_states.values["TODO"] == 1

    assert "python" in result.tag_frequencies
    assert result.tag_frequencies["python"].total == 3

    assert result.timerange.earliest == datetime(2023, 10, 18, 9, 15)
    assert result.timerange.latest == datetime(2023, 10, 20, 14, 43)


def test_analyze_avg_tasks_per_day_with_multiple_done_keys() -> None:
    """Test that average tasks per day counts all done states."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task 2
CLOSED: [2023-10-18 Wed 10:00]

* ARCHIVED Task 3
CLOSED: [2023-10-20 Fri 14:43]
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.avg_tasks_per_day == 3.0 / 3


def test_analyze_max_single_day_with_multiple_done_keys() -> None:
    """Test that max single day count considers all done states."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task 2
CLOSED: [2023-10-18 Wed 10:00]

* ARCHIVED Task 3
CLOSED: [2023-10-18 Wed 14:43]

* DONE Task 4
CLOSED: [2023-10-20 Fri 16:00]
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.max_single_day_count == 3


def test_analyze_max_repeat_count_with_multiple_done_keys() -> None:
    """Test that max repeat count considers all done states."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 09:10]
- State "ARCHIVED"   from "TODO"       [2023-10-18 Wed 09:05]
- State "DONE"       from "TODO"       [2023-10-17 Tue 09:00]
:END:
""")

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.max_repeat_count == 4


def test_analyze_task_days_with_multiple_done_keys() -> None:
    """Test that task day histogram includes all done states."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-20 Fri 14:43]

* CANCELLED Task 2
CLOSED: [2023-10-21 Sat 10:00]

* ARCHIVED Task 3
CLOSED: [2023-10-22 Sun 15:30]
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.task_days.values["Friday"] == 1
    assert result.task_days.values["Saturday"] == 1
    assert result.task_days.values["Sunday"] == 1


def test_analyze_relations_with_multiple_done_keys() -> None:
    """Test that tag relations count all done states."""
    nodes = node_from_org(
        """
* DONE Task :python:testing:
* CANCELLED Task :python:testing:
* ARCHIVED Task :python:testing:
* TODO Task :python:testing:
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert "python" in result.tag_relations
    assert "testing" in result.tag_relations
    assert result.tag_relations["python"].relations["testing"] == 3
    assert result.tag_relations["testing"].relations["python"] == 3


def test_analyze_time_ranges_with_multiple_done_keys() -> None:
    """Test that time ranges include all done states."""
    nodes = node_from_org(
        """
* DONE Task :python:
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task :python:
CLOSED: [2023-10-20 Fri 14:43]

* ARCHIVED Task :testing:
CLOSED: [2023-10-22 Sun 16:00]

* TODO Task :python:
CLOSED: [2023-10-25 Wed 12:00]
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert "python" in result.tag_time_ranges
    assert "testing" in result.tag_time_ranges

    python_tr = result.tag_time_ranges["python"]
    assert python_tr.earliest == datetime(2023, 10, 18, 9, 15)
    assert python_tr.latest == datetime(2023, 10, 20, 14, 43)

    testing_tr = result.tag_time_ranges["testing"]
    assert testing_tr.earliest == datetime(2023, 10, 22, 16, 0)
    assert testing_tr.latest == datetime(2023, 10, 22, 16, 0)


def test_analyze_only_specified_done_keys_counted() -> None:
    """Test that only tasks with specified done keys are counted."""
    nodes = node_from_org(
        """
* DONE Task :tag1:
* CANCELLED Task :tag2:
* ARCHIVED Task :tag3:
* TODO Task :tag4:
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result_done_only = analyze(nodes, {}, category="tags", max_relations=3, done_keys=["DONE"])
    assert "tag1" in result_done_only.tag_frequencies
    assert "tag2" not in result_done_only.tag_frequencies
    assert "tag3" not in result_done_only.tag_frequencies
    assert "tag4" not in result_done_only.tag_frequencies

    result_all = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )
    assert "tag1" in result_all.tag_frequencies
    assert "tag2" in result_all.tag_frequencies
    assert "tag3" in result_all.tag_frequencies
    assert "tag4" not in result_all.tag_frequencies


def test_analyze_done_count_sum_multiple_keys() -> None:
    """Test that done_count correctly sums all done_keys from task_states."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:00]

* DONE Task 2
CLOSED: [2023-10-18 Wed 10:00]

* CANCELLED Task 3
CLOSED: [2023-10-19 Thu 09:00]

* CANCELLED Task 4
CLOSED: [2023-10-19 Thu 10:00]

* CANCELLED Task 5
CLOSED: [2023-10-19 Thu 11:00]

* ARCHIVED Task 6
CLOSED: [2023-10-20 Fri 09:00]

* TODO Task 7
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.task_states.values["DONE"] == 2
    assert result.task_states.values["CANCELLED"] == 3
    assert result.task_states.values["ARCHIVED"] == 1
    assert result.task_states.values["TODO"] == 1

    total_done = 2 + 3 + 1
    assert result.timerange.earliest is not None
    assert result.timerange.latest is not None
    days_spanned = (result.timerange.latest.date() - result.timerange.earliest.date()).days + 1
    expected_avg = total_done / days_spanned
    assert result.avg_tasks_per_day == expected_avg


def test_analyze_custom_completion_states() -> None:
    """Test with completely custom completion state names."""
    nodes = node_from_org(
        """
* COMPLETED Task :tag1:
* FINISHED Task :tag2:
* RESOLVED Task :tag3:
* INPROGRESS Task :tag4:
""",
        todo_keys=["INPROGRESS"],
        done_keys=["COMPLETED", "FINISHED", "RESOLVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["COMPLETED", "FINISHED", "RESOLVED"]
    )

    assert "tag1" in result.tag_frequencies
    assert "tag2" in result.tag_frequencies
    assert "tag3" in result.tag_frequencies
    assert "tag4" not in result.tag_frequencies
    assert result.tag_frequencies["tag1"].total == 1
    assert result.tag_frequencies["tag2"].total == 1
    assert result.tag_frequencies["tag3"].total == 1


def test_analyze_groups_with_multiple_done_keys() -> None:
    """Test that tag groups are computed correctly with multiple done keys."""
    nodes = node_from_org(
        """
* DONE Task :a:b:
* CANCELLED Task :b:c:
* ARCHIVED Task :c:a:
* DONE Task :a:c:
* TODO Task :a:b:c:
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )

    assert result.tag_relations["a"].relations["b"] == 1
    assert result.tag_relations["b"].relations["c"] == 1
    assert result.tag_relations["c"].relations["a"] == 2
    assert result.tag_relations["a"].relations["c"] == 2
    assert len(result.tag_groups) > 0


def test_analyze_empty_done_keys() -> None:
    """Test that empty done_keys list results in no frequencies."""
    nodes = node_from_org("""
* DONE Task :tag1:
* CANCELLED Task :tag2:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, done_keys=[])

    assert result.tag_frequencies == {}
    assert result.tag_relations == {}
    assert result.tag_time_ranges == {}
    assert result.timerange.earliest is None
    assert result.timerange.latest is None


def test_analyze_heading_and_body_with_multiple_done_keys() -> None:
    """Test that heading and body analysis work with multiple done keys."""
    nodes = node_from_org(
        """
* DONE Implement feature :tag1:
Feature implementation

* CANCELLED Fix bug :tag2:
Bug fixing

* ARCHIVED Update docs :tag3:
Documentation update
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    result_tags = analyze(
        nodes, {}, category="tags", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )
    assert len(result_tags.tag_frequencies) == 3

    result_heading = analyze(
        nodes, {}, category="heading", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )
    assert "implement" in result_heading.tag_frequencies
    assert "fix" in result_heading.tag_frequencies
    assert "update" in result_heading.tag_frequencies

    result_body = analyze(
        nodes, {}, category="body", max_relations=3, done_keys=["DONE", "CANCELLED", "ARCHIVED"]
    )
    assert "feature" in result_body.tag_frequencies
    assert "bug" in result_body.tag_frequencies
    assert "documentation" in result_body.tag_frequencies
