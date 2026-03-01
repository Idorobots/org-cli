"""Unit tests for individual filter functions."""

from collections.abc import Callable
from datetime import date, datetime

import pytest
from orgparse.node import OrgNode

from org.filters import (
    filter_body,
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_heading,
    filter_not_completed,
    filter_property,
    filter_repeats_above,
    filter_repeats_below,
    filter_tag,
    get_repeat_count,
)
from tests.conftest import node_from_org


def test_get_repeat_count_no_repeats() -> None:
    """Test get_repeat_count with no repeated tasks."""
    nodes = node_from_org("* DONE Task\n")
    assert get_repeat_count(nodes[0]) == 1


def test_get_repeat_count_with_repeats() -> None:
    """Test get_repeat_count with repeated tasks."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-12 Sun 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    assert get_repeat_count(nodes[0]) == 2


@pytest.mark.parametrize(
    "filter_func,threshold,should_match",
    [
        (filter_repeats_above, 1, True),
        (filter_repeats_above, 2, False),
        (filter_repeats_below, 3, True),
        (filter_repeats_below, 1, False),
    ],
)
def test_filter_repeats_boundary(
    filter_func: Callable[[list[OrgNode], int], list[OrgNode]], threshold: int, should_match: bool
) -> None:
    """Test repeats filters are non-inclusive at boundaries."""
    org_text_2_repeats = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-12 Sun 11:00]
:END:
"""
    nodes = node_from_org(org_text_2_repeats)

    result = filter_func(nodes, threshold)

    assert len(result) == (1 if should_match else 0)


def test_filter_repeats_above_minimum_is_one() -> None:
    """Test filter_repeats_above where minimum repeat count is 1."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_repeats_above(nodes, 0)

    assert len(result) == 1


@pytest.mark.parametrize(
    "filter_func,cutoff_date,expected_task",
    [
        (filter_date_from, datetime(2025, 1, 31), "feb"),
        (filter_date_until, datetime(2025, 2, 1), "jan"),
    ],
)
def test_filter_date_basic(
    filter_func: Callable[[list[OrgNode], datetime], list[OrgNode]],
    cutoff_date: datetime,
    expected_task: str,
) -> None:
    """Test date filters with basic date filtering."""
    org_text_jan = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    org_text_feb = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"

    nodes = node_from_org(org_text_jan) + node_from_org(org_text_feb)

    result = filter_func(nodes, cutoff_date)

    assert len(result) == 1
    assert result[0] == (nodes[1] if expected_task == "feb" else nodes[0])


@pytest.mark.parametrize(
    "filter_func,cutoff_date",
    [
        (filter_date_from, datetime(2025, 1, 15)),
        (filter_date_until, datetime(2025, 1, 15, 10, 0)),
    ],
)
def test_filter_date_boundary_inclusive(
    filter_func: Callable[[list[OrgNode], datetime], list[OrgNode]], cutoff_date: datetime
) -> None:
    """Test date filters are inclusive at boundaries."""
    org_text = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    nodes = node_from_org(org_text)

    result = filter_func(nodes, cutoff_date)

    assert len(result) == 1


@pytest.mark.parametrize("filter_func", [filter_date_from, filter_date_until])
def test_filter_date_no_timestamp(
    filter_func: Callable[[list[OrgNode], datetime], list[OrgNode]],
) -> None:
    """Test date filters exclude nodes without timestamps."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_func(nodes, datetime(2025, 1, 1))

    assert len(result) == 0


def test_filter_date_from_multiple_timestamps() -> None:
    """Test filter_date_from with repeated tasks (multiple timestamps)."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 1


def test_filter_date_from_todo_task() -> None:
    """Test filter_date_from includes TODO tasks with timestamps."""
    org_text = "* TODO Task\nSCHEDULED: <2025-01-20 Mon>\n"
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 1, 15))

    assert len(result) == 1


def test_filter_date_until_todo_task() -> None:
    """Test filter_date_until includes TODO tasks with timestamps."""
    org_text = "* TODO Task\nSCHEDULED: <2025-01-10 Fri>\n"
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, datetime(2025, 1, 15))

    assert len(result) == 1


def test_filter_date_from_mixed_completion_states() -> None:
    """Test filter_date_from includes tasks regardless of completion state."""
    org_text_done = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"
    org_text_todo = "* TODO Task\nSCHEDULED: <2025-02-20 Thu>\n"
    org_text_cancelled = "* CANCELLED Task\nCLOSED: [2025-02-25 Tue 14:00]\n"

    nodes = (
        node_from_org(org_text_done)
        + node_from_org(org_text_todo)
        + node_from_org(org_text_cancelled)
    )

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 3


@pytest.mark.parametrize(
    "filter_func,cutoff_date,expected_repeat_count,expected_date",
    [
        (filter_date_from, datetime(2025, 2, 1), 2, None),
        (filter_date_from, datetime(2025, 2, 1), 1, date(2025, 2, 15)),
        (filter_date_from, datetime(2025, 2, 1), 1, date(2025, 2, 1)),
        (filter_date_until, datetime(2025, 2, 1), 2, None),
        (filter_date_until, datetime(2025, 2, 1), 1, date(2025, 1, 10)),
        (filter_date_until, datetime(2025, 2, 1, 9, 0), 1, date(2025, 2, 1)),
    ],
)
def test_filter_date_with_repeats(
    filter_func: Callable[[list[OrgNode], datetime], list[OrgNode]],
    cutoff_date: datetime,
    expected_repeat_count: int,
    expected_date: date | None,
) -> None:
    """Test date filters with repeated tasks."""
    if filter_func == filter_date_from:
        if expected_repeat_count == 2:
            org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-10 Mon 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
        elif expected_date == date(2025, 2, 15):
            org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
        else:
            org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-31 Fri 09:00]
- State "DONE" from "TODO" [2025-02-01 Sat 11:00]
:END:
"""
    elif expected_repeat_count == 2:
        org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-15 Wed 11:00]
:END:
"""
    elif expected_date == date(2025, 1, 10):
        org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    else:
        org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-01 Sat 09:00]
- State "DONE" from "TODO" [2025-02-02 Sun 11:00]
:END:
"""

    nodes = node_from_org(org_text)

    result = filter_func(nodes, cutoff_date)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == expected_repeat_count
    if expected_date:
        assert result[0].repeated_tasks[0].start.date() == expected_date


def test_filter_date_from_repeats_none_match() -> None:
    """Test filter_date_from with repeated tasks where none match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-15 Wed 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 0


def test_filter_date_until_repeats_none_match() -> None:
    """Test filter_date_until with repeated tasks where none match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-10 Mon 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, datetime(2025, 2, 1))

    assert len(result) == 0


def test_filter_property_basic() -> None:
    """Test filter_property with basic property matching."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:custom_prop: value1\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:custom_prop: value2\n:END:\n")
        + node_from_org("* DONE Task\n")
    )

    result = filter_property(nodes, "custom_prop", "value1")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_property_case_sensitive() -> None:
    """Test filter_property is case-sensitive."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:CaseProp: CaseValue\n:END:\n")

    result_exact = filter_property(nodes, "CaseProp", "CaseValue")
    result_wrong_name = filter_property(nodes, "caseprop", "CaseValue")
    result_wrong_value = filter_property(nodes, "CaseProp", "casevalue")

    assert len(result_exact) == 1
    assert len(result_wrong_name) == 0
    assert len(result_wrong_value) == 0


def test_filter_property_with_equals_in_value() -> None:
    """Test filter_property with equals sign in value."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:equation: E=mc^2\n:END:\n")

    result = filter_property(nodes, "equation", "E=mc^2")

    assert len(result) == 1


def test_filter_property_missing_property() -> None:
    """Test filter_property excludes nodes without the property."""
    nodes = node_from_org(
        "* DONE Task\n:PROPERTIES:\n:custom_prop: value1\n:END:\n"
    ) + node_from_org("* DONE Task\n")

    result = filter_property(nodes, "custom_prop", "value1")

    assert len(result) == 1


def test_filter_property_gamify_exp_not_defaulted() -> None:
    """Test filter_property does not default missing gamify_exp to 10."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_property(nodes, "gamify_exp", "10")

    assert len(result) == 0


def test_filter_tag_basic() -> None:
    """Test filter_tag with basic tag matching."""
    nodes = (
        node_from_org("* DONE Task :tag1:\n")
        + node_from_org("* DONE Task :tag2:\n")
        + node_from_org("* DONE Task\n")
    )

    result = filter_tag(nodes, "tag1")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_tag_case_sensitive() -> None:
    """Test filter_tag is case-sensitive."""
    nodes = node_from_org("* DONE Task :CaseSensitive:\n")

    result_exact = filter_tag(nodes, "CaseSensitive")
    result_wrong = filter_tag(nodes, "casesensitive")

    assert len(result_exact) == 1
    assert len(result_wrong) == 0


def test_filter_tag_multiple_tags() -> None:
    """Test filter_tag matches individual tag from multiple tags."""
    nodes = node_from_org("* DONE Task :tag1:tag2:tag3:\n")

    result = filter_tag(nodes, "tag2")

    assert len(result) == 1


def test_filter_tag_no_tag() -> None:
    """Test filter_tag excludes nodes without the tag."""
    nodes = (
        node_from_org("* DONE Task :tag1:\n")
        + node_from_org("* DONE Task :tag2:\n")
        + node_from_org("* DONE Task\n")
    )

    result = filter_tag(nodes, "tag3")

    assert len(result) == 0


@pytest.mark.parametrize(
    "filter_func,expected_indices",
    [
        (filter_completed, [0, 2]),
        (filter_not_completed, [1, 2]),
    ],
)
def test_filter_completion_basic(
    filter_func: Callable[[list[OrgNode]], list[OrgNode]], expected_indices: list[int]
) -> None:
    """Test completion filters with basic filtering."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* TODO Task\n")
        + node_from_org(
            "* DONE Another\n"
            if 2 in expected_indices and filter_func == filter_completed
            else "* TODO Another\n"
        )
    )

    result = filter_func(nodes)

    assert len(result) == len(expected_indices)
    for i, idx in enumerate(expected_indices):
        assert result[i] == nodes[idx]


@pytest.mark.parametrize(
    "filter_func,done_keys,todo_keys",
    [
        (filter_completed, ["DONE", "DELEGATED"], ["TODO"]),
        (filter_not_completed, ["DONE"], ["TODO", "WAITING"]),
    ],
)
def test_filter_completion_multiple_keys(
    filter_func: Callable[[list[OrgNode]], list[OrgNode]],
    done_keys: list[str],
    todo_keys: list[str],
) -> None:
    """Test completion filters with multiple todo/done keys."""
    if filter_func == filter_completed:
        nodes = node_from_org(
            "* DONE Task\n",
            todo_keys=todo_keys,
            done_keys=done_keys,
        ) + node_from_org(
            "* DELEGATED Task\n",
            todo_keys=todo_keys,
            done_keys=done_keys,
        )
    else:
        nodes = node_from_org("* TODO Task\n", todo_keys=todo_keys) + node_from_org(
            "* WAITING Task\n", todo_keys=todo_keys
        )

    result = filter_func(nodes)

    assert len(result) == 2


@pytest.mark.parametrize(
    "filter_func,todo_state",
    [
        (filter_completed, "TODO"),
        (filter_not_completed, "DONE"),
    ],
)
def test_filter_completion_no_match(
    filter_func: Callable[[list[OrgNode]], list[OrgNode]], todo_state: str
) -> None:
    """Test completion filters with no matching nodes."""
    nodes = node_from_org(f"* {todo_state} Task\n")

    result = filter_func(nodes)

    assert len(result) == 0


def test_filters_preserve_order() -> None:
    """Test that all filters preserve original node order."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org(
            '* DONE Task\n:LOGBOOK:\n- State "DONE" from "TODO" [2025-01-12 Sun 11:00]\n:END:\n'
        )
        + node_from_org(
            '* DONE Task\n:LOGBOOK:\n- State "DONE" from "TODO" [2025-01-13 Mon 11:00]\n- State "DONE" from "TODO" [2025-01-14 Tue 11:00]\n:END:\n'
        )
    )

    result = filter_repeats_above(nodes, 0)

    assert len(result) == 3
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]
    assert result[2] == nodes[2]


def test_filter_date_range_repeats_combined() -> None:
    """Test combining date_from and date_until filters on repeated tasks."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
- State "DONE" from "TODO" [2025-03-20 Thu 14:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))
    result = filter_date_until(result, datetime(2025, 3, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].start.date() == date(2025, 2, 15)


def test_filters_do_not_mutate_original_nodes() -> None:
    """Test that filtering with repeats does not mutate original nodes."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_repeat_count = len(nodes[0].repeated_tasks)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(nodes[0].repeated_tasks) == original_repeat_count
    assert len(result[0].repeated_tasks) == 1


@pytest.mark.parametrize(
    "filter_func,expected_repeat_count",
    [
        (filter_completed, 2),
        (filter_completed, 1),
        (filter_completed, 0),
        (filter_not_completed, 2),
        (filter_not_completed, 1),
        (filter_not_completed, 0),
    ],
)
def test_filter_completion_with_repeats(
    filter_func: Callable[[list[OrgNode]], list[OrgNode]], expected_repeat_count: int
) -> None:
    """Test completion filters with repeated tasks."""
    if filter_func == filter_completed:
        if expected_repeat_count == 2:
            org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
        elif expected_repeat_count == 1:
            org_text = """* TODO Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
        else:
            org_text = """* TODO Task
:LOGBOOK:
- State "TODO" from "DONE" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    elif expected_repeat_count == 2:
        org_text = """* TODO Task
:LOGBOOK:
- State "TODO" from "DONE" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    elif expected_repeat_count == 1:
        org_text = """* DONE Task
:LOGBOOK:
- State "TODO" from "DONE" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    else:
        org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""

    nodes = node_from_org(org_text, todo_keys=["TODO"])

    result = filter_func(nodes)

    if expected_repeat_count == 0:
        assert len(result) == 0
    else:
        assert len(result) == 1
        assert len(result[0].repeated_tasks) == expected_repeat_count


def test_filter_completed_without_repeats_matches() -> None:
    """Test filter_completed with non-repeating task that is DONE."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 0


def test_filter_not_completed_without_repeats_matches() -> None:
    """Test filter_not_completed with non-repeating task that is TODO."""
    nodes = node_from_org("* TODO Task\n")

    result = filter_not_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 0


def test_filter_completed_multiple_done_keys_with_repeats() -> None:
    """Test filter_completed with multiple done keys and repeated tasks."""
    org_text = """* DELEGATED Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DELEGATED" from "TODO" [2025-02-15 Sat 11:00]
- State "CANCELLED" from "TODO" [2025-03-20 Thu 14:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"], done_keys=["DONE", "DELEGATED"])

    result = filter_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 2
    assert result[0].repeated_tasks[0].after in ["DONE", "DELEGATED"]
    assert result[0].repeated_tasks[1].after in ["DONE", "DELEGATED"]


@pytest.mark.parametrize(
    "pattern,expected_count,expected_indices",
    [
        (".*ing", 3, [0, 1, 2]),
        ("^test$", 1, [0]),
        ("^testing$", 1, [1]),
        ("^Testing$", 1, [0]),
        ("^bar$", 1, [0]),
        ("^baz$", 1, [0]),
        ("foo", 3, [0, 1, 2]),
        ("^test", 2, [0, 2]),
        ("ing$", 2, [0, 2]),
        ("test[0-9]", 2, [0, 1]),
        ("bug|fix", 2, [0, 1]),
    ],
)
def test_filter_tag_regex(pattern: str, expected_count: int, expected_indices: list[int]) -> None:
    """Test filter_tag with various regex patterns."""
    if pattern == ".*ing":
        nodes = (
            node_from_org("* DONE Task :testing:\n")
            + node_from_org("* DONE Task :debugging:\n")
            + node_from_org("* DONE Task :coding:\n")
        )
    elif pattern in ["^test$", "^testing$"]:
        nodes = (
            node_from_org("* DONE Task :test:\n")
            + node_from_org("* DONE Task :testing:\n")
            + node_from_org("* DONE Task :test123:\n")
        )
    elif pattern in ["^testing$", "^Testing$"]:
        nodes = node_from_org("* DONE Task :Testing:\n") + node_from_org("* DONE Task :testing:\n")
    elif pattern in ["^bar$", "^baz$"]:
        nodes = node_from_org("* DONE Task :foo:bar:baz:\n")
    elif pattern == "foo":
        nodes = (
            node_from_org("* DONE Task :foobar:\n")
            + node_from_org("* DONE Task :foo:\n")
            + node_from_org("* DONE Task :barfoo:\n")
        )
    elif pattern == "^test":
        nodes = (
            node_from_org("* DONE Task :testing:\n")
            + node_from_org("* DONE Task :mytesting:\n")
            + node_from_org("* DONE Task :test:\n")
        )
    elif pattern == "ing$":
        nodes = (
            node_from_org("* DONE Task :testing:\n")
            + node_from_org("* DONE Task :testingmore:\n")
            + node_from_org("* DONE Task :debugging:\n")
        )
    elif pattern == "test[0-9]":
        nodes = (
            node_from_org("* DONE Task :test1:\n")
            + node_from_org("* DONE Task :test2:\n")
            + node_from_org("* DONE Task :testa:\n")
        )
    else:
        nodes = (
            node_from_org("* DONE Task :bug:\n")
            + node_from_org("* DONE Task :fix:\n")
            + node_from_org("* DONE Task :feature:\n")
        )

    result = filter_tag(nodes, pattern)

    assert len(result) == expected_count
    for i, idx in enumerate(expected_indices):
        assert result[i] == nodes[idx]


@pytest.mark.parametrize(
    "filter_func,pattern,expected_count,expected_indices",
    [
        (filter_heading, "Fix", 2, [0, 2]),
        (filter_heading, "fix", 1, [1]),
        (filter_heading, r"\btest\b", 2, [0, 2]),
        (filter_heading, "bug|issue", 2, [0, 1]),
        (filter_heading, "nonexistent", 0, []),
        (filter_body, "test", 1, [0]),
        (filter_body, "Test", 1, [0]),
        (filter_body, "^Second", 1, [0]),
        (filter_body, "two$", 1, [0]),
        (filter_body, "First.*Second", 0, []),
        (filter_body, "TODO|FIXME", 2, [0, 1]),
        (filter_body, "nonexistent", 0, []),
    ],
)
def test_filter_regex_patterns(
    filter_func: Callable[[list[OrgNode], str], list[OrgNode]],
    pattern: str,
    expected_count: int,
    expected_indices: list[int],
) -> None:
    """Test heading and body filters with regex patterns."""
    if filter_func == filter_heading:
        if pattern in ["Fix", "fix"]:
            nodes = (
                node_from_org("* DONE Fix Bug\n")
                + node_from_org("* DONE fix bug\n")
                + node_from_org("* DONE Fix typo\n")
            )
        elif pattern == r"\btest\b":
            nodes = (
                node_from_org("* DONE test the feature\n")
                + node_from_org("* DONE testing feature\n")
                + node_from_org("* DONE test\n")
            )
        elif pattern == "bug|issue":
            nodes = (
                node_from_org("* DONE Fix bug\n")
                + node_from_org("* DONE Resolve issue\n")
                + node_from_org("* DONE Add feature\n")
            )
        else:
            nodes = node_from_org("* DONE Task\n")
    elif pattern == "test":
        nodes = node_from_org("* DONE Task\ntest body\n") + node_from_org(
            "* DONE Task\nTest Body\n"
        )
    elif pattern == "Test":
        nodes = node_from_org("* DONE Task\nTest Body\n") + node_from_org(
            "* DONE Task\ntest body\n"
        )
    elif pattern in ["^Second", "two$", "First.*Second"]:
        org_text = """* DONE Task
First line
Second line
Third line
"""
        if pattern == "two$":
            org_text = """* DONE Task
Line one
Line two
Line three
"""
        nodes = node_from_org(org_text)
    elif pattern == "TODO|FIXME":
        nodes = (
            node_from_org("* DONE Task\nContains TODO\n")
            + node_from_org("* DONE Task\nContains FIXME\n")
            + node_from_org("* DONE Task\nContains nothing\n")
        )
    else:
        nodes = node_from_org("* DONE Task\nBody content\n")

    result = filter_func(nodes, pattern)

    assert len(result) == expected_count
    for i, idx in enumerate(expected_indices):
        assert result[i] == nodes[idx]


def test_filter_heading_empty_heading() -> None:
    """Test filter_heading handles nodes with empty heading."""
    nodes = node_from_org("* DONE\n")

    result = filter_heading(nodes, "test")

    assert len(result) == 0


def test_filter_body_empty_body() -> None:
    """Test filter_body handles nodes with no body."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_body(nodes, "test")

    assert len(result) == 0
