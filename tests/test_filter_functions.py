"""Unit tests for individual filter functions."""

from datetime import date, datetime

import orgparse

from orgstats.filters import (
    filter_body,
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_gamify_exp_above,
    filter_gamify_exp_below,
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


def test_filter_gamify_exp_above_basic() -> None:
    """Test filter_gamify_exp_above with basic values."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
    )

    result = filter_gamify_exp_above(nodes, 10)

    assert len(result) == 2
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]


def test_filter_gamify_exp_above_boundary() -> None:
    """Test filter_gamify_exp_above with boundary value (non-inclusive)."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n") + node_from_org(
        "* DONE Task\n:PROPERTIES:\n:gamify_exp: 11\n:END:\n"
    )

    result = filter_gamify_exp_above(nodes, 10)

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_filter_gamify_exp_above_missing_defaults_to_10() -> None:
    """Test filter_gamify_exp_above with missing gamify_exp (defaults to 10)."""
    nodes = node_from_org("* DONE Task\n") + node_from_org(
        "* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n"
    )

    result = filter_gamify_exp_above(nodes, 9)

    assert len(result) == 2


def test_filter_gamify_exp_above_empty_list() -> None:
    """Test filter_gamify_exp_above with empty list."""
    nodes: list[orgparse.node.OrgNode] = []

    result = filter_gamify_exp_above(nodes, 10)

    assert result == []


def test_filter_gamify_exp_below_basic() -> None:
    """Test filter_gamify_exp_below with basic values."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
    )

    result = filter_gamify_exp_below(nodes, 20)

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_gamify_exp_below_boundary() -> None:
    """Test filter_gamify_exp_below with boundary value (non-inclusive)."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 9\n:END:\n") + node_from_org(
        "* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n"
    )

    result = filter_gamify_exp_below(nodes, 10)

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_gamify_exp_below_missing_defaults_to_10() -> None:
    """Test filter_gamify_exp_below with missing gamify_exp (defaults to 10)."""
    nodes = node_from_org("* DONE Task\n") + node_from_org(
        "* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n"
    )

    result = filter_gamify_exp_below(nodes, 11)

    assert len(result) == 2


def test_filter_repeats_above_basic() -> None:
    """Test filter_repeats_above with basic values."""
    org_text_2_repeats = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-12 Sun 11:00]
:END:
"""
    nodes = node_from_org("* DONE Task\n") + node_from_org(org_text_2_repeats)

    result = filter_repeats_above(nodes, 1)

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_filter_repeats_above_boundary() -> None:
    """Test filter_repeats_above with boundary value (non-inclusive)."""
    org_text_2_repeats = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-12 Sun 11:00]
:END:
"""
    nodes = node_from_org(org_text_2_repeats)

    result = filter_repeats_above(nodes, 2)

    assert len(result) == 0


def test_filter_repeats_above_minimum_is_one() -> None:
    """Test filter_repeats_above where minimum repeat count is 1."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_repeats_above(nodes, 0)

    assert len(result) == 1


def test_filter_repeats_below_basic() -> None:
    """Test filter_repeats_below with basic values."""
    org_text_3_repeats = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-12 Sun 11:00]
- State "DONE" from "TODO" [2025-01-14 Tue 15:00]
:END:
"""
    nodes = node_from_org("* DONE Task\n") + node_from_org(org_text_3_repeats)

    result = filter_repeats_below(nodes, 2)

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_repeats_below_boundary() -> None:
    """Test filter_repeats_below with boundary value (non-inclusive)."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_repeats_below(nodes, 1)

    assert len(result) == 0


def test_filter_date_from_basic() -> None:
    """Test filter_date_from with basic date filtering."""
    org_text_jan = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    org_text_feb = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"

    nodes = node_from_org(org_text_jan) + node_from_org(org_text_feb)

    result = filter_date_from(nodes, datetime(2025, 1, 31))

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_filter_date_from_boundary() -> None:
    """Test filter_date_from with boundary date (inclusive)."""
    org_text = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 1, 15))

    assert len(result) == 1


def test_filter_date_from_no_timestamp() -> None:
    """Test filter_date_from excludes nodes without timestamps."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_date_from(nodes, datetime(2025, 1, 1))

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


def test_filter_date_until_basic() -> None:
    """Test filter_date_until with basic date filtering."""
    org_text_jan = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    org_text_feb = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"

    nodes = node_from_org(org_text_jan) + node_from_org(org_text_feb)

    result = filter_date_until(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_date_until_boundary() -> None:
    """Test filter_date_until with boundary date (inclusive)."""
    org_text = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, datetime(2025, 1, 15, 10, 00))

    assert len(result) == 1


def test_filter_date_until_no_timestamp() -> None:
    """Test filter_date_until excludes nodes without timestamps."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_date_until(nodes, datetime(2025, 12, 31))

    assert len(result) == 0


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


def test_filter_date_from_repeated_tasks_all_states() -> None:
    """Test filter_date_from includes all repeated tasks regardless of state."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-01-15 Wed 11:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1


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


def test_filter_completed_basic() -> None:
    """Test filter_completed with basic completion filtering."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* TODO Task\n")
        + node_from_org("* DONE Another\n")
    )

    result = filter_completed(nodes)

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[2]


def test_filter_completed_multiple_done_keys() -> None:
    """Test filter_completed with multiple done keys."""
    nodes = node_from_org(
        "* DONE Task\n", todo_keys=["TODO"], done_keys=["DONE", "DELEGATED"]
    ) + node_from_org("* DELEGATED Task\n", todo_keys=["TODO"], done_keys=["DONE", "DELEGATED"])

    result = filter_completed(nodes)

    assert len(result) == 2


def test_filter_completed_no_match() -> None:
    """Test filter_completed with no matching nodes."""
    nodes = node_from_org("* TODO Task\n")

    result = filter_completed(nodes)

    assert len(result) == 0


def test_filter_not_completed_basic() -> None:
    """Test filter_not_completed with basic filtering."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* TODO Task\n")
        + node_from_org("* TODO Another\n")
    )

    result = filter_not_completed(nodes)

    assert len(result) == 2
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]


def test_filter_not_completed_multiple_todo_keys() -> None:
    """Test filter_not_completed with multiple todo keys."""
    nodes = node_from_org(
        "* TODO Task\n", todo_keys=["TODO", "WAITING"], done_keys=["DONE"]
    ) + node_from_org("* WAITING Task\n", todo_keys=["TODO", "WAITING"], done_keys=["DONE"])

    result = filter_not_completed(nodes)

    assert len(result) == 2


def test_filter_not_completed_no_match() -> None:
    """Test filter_not_completed with no matching nodes."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_not_completed(nodes)

    assert len(result) == 0


def test_filters_preserve_order() -> None:
    """Test that all filters preserve original node order."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 35\n:END:\n")
    )

    result = filter_gamify_exp_above(nodes, 10)

    assert len(result) == 3
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]
    assert result[2] == nodes[2]


def test_filter_date_from_repeats_all_match() -> None:
    """Test filter_date_from with repeated tasks where all match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-10 Mon 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 2


def test_filter_date_from_repeats_some_match() -> None:
    """Test filter_date_from with repeated tasks where some match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].start.date() == date(2025, 2, 15)


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


def test_filter_date_from_repeats_boundary() -> None:
    """Test filter_date_from with repeated tasks at boundary (inclusive)."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-31 Fri 09:00]
- State "DONE" from "TODO" [2025-02-01 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].start.date() == date(2025, 2, 1)


def test_filter_date_from_repeats_mixed_states() -> None:
    """Test filter_date_from includes all repeats by date regardless of state."""
    org_text = """* TODO Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-10 Mon 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"], done_keys=["DONE"])

    result = filter_date_from(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 2


def test_filter_date_until_repeats_all_match() -> None:
    """Test filter_date_until with repeated tasks where all match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-15 Wed 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 2


def test_filter_date_until_repeats_some_match() -> None:
    """Test filter_date_until with repeated tasks where some match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, datetime(2025, 2, 1))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].start.date() == date(2025, 1, 10)


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


def test_filter_date_until_repeats_boundary() -> None:
    """Test filter_date_until with repeated tasks at boundary (inclusive)."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-01 Sat 09:00]
- State "DONE" from "TODO" [2025-02-02 Sun 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, datetime(2025, 2, 1, 9, 0))

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].start.date() == date(2025, 2, 1)


def test_filter_completed_repeats_all_match() -> None:
    """Test filter_completed with repeated tasks where all are DONE."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 2


def test_filter_completed_repeats_some_match() -> None:
    """Test filter_completed with repeated tasks where some are DONE."""
    org_text = """* TODO Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"], done_keys=["DONE"])

    result = filter_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].after == "DONE"


def test_filter_completed_repeats_none_match() -> None:
    """Test filter_completed with repeated tasks where none are DONE."""
    org_text = """* TODO Task
:LOGBOOK:
- State "TODO" from "DONE" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"], done_keys=["DONE"])

    result = filter_completed(nodes)

    assert len(result) == 0


def test_filter_completed_without_repeats_matches() -> None:
    """Test filter_completed with non-repeating task that is DONE."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 0


def test_filter_completed_without_repeats_no_match() -> None:
    """Test filter_completed with non-repeating task that is TODO."""
    nodes = node_from_org("* TODO Task\n")

    result = filter_completed(nodes)

    assert len(result) == 0


def test_filter_not_completed_repeats_all_match() -> None:
    """Test filter_not_completed with repeated tasks where all are TODO."""
    org_text = """* TODO Task
:LOGBOOK:
- State "TODO" from "DONE" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"], done_keys=["DONE"])

    result = filter_not_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 2


def test_filter_not_completed_repeats_some_match() -> None:
    """Test filter_not_completed with repeated tasks where some are TODO."""
    org_text = """* DONE Task
:LOGBOOK:
- State "TODO" from "DONE" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"], done_keys=["DONE"])

    result = filter_not_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 1
    assert result[0].repeated_tasks[0].after == "TODO"


def test_filter_not_completed_repeats_none_match() -> None:
    """Test filter_not_completed with repeated tasks where none are TODO."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    result = filter_not_completed(nodes)

    assert len(result) == 0


def test_filter_not_completed_without_repeats_matches() -> None:
    """Test filter_not_completed with non-repeating task that is TODO."""
    nodes = node_from_org("* TODO Task\n")

    result = filter_not_completed(nodes)

    assert len(result) == 1
    assert len(result[0].repeated_tasks) == 0


def test_filter_not_completed_without_repeats_no_match() -> None:
    """Test filter_not_completed with non-repeating task that is DONE."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_not_completed(nodes)

    assert len(result) == 0


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


def test_filter_tag_regex_basic() -> None:
    """Test filter_tag with basic regex patterns."""
    nodes = (
        node_from_org("* DONE Task :testing:\n")
        + node_from_org("* DONE Task :debugging:\n")
        + node_from_org("* DONE Task :coding:\n")
    )

    result = filter_tag(nodes, ".*ing")

    assert len(result) == 3


def test_filter_tag_regex_exact_match() -> None:
    """Test filter_tag with exact match using anchors."""
    nodes = (
        node_from_org("* DONE Task :test:\n")
        + node_from_org("* DONE Task :testing:\n")
        + node_from_org("* DONE Task :test123:\n")
    )

    result = filter_tag(nodes, "^test$")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_tag_regex_case_sensitive() -> None:
    """Test filter_tag is case-sensitive."""
    nodes = node_from_org("* DONE Task :Testing:\n") + node_from_org("* DONE Task :testing:\n")

    result_lower = filter_tag(nodes, "^testing$")
    result_upper = filter_tag(nodes, "^Testing$")

    assert len(result_lower) == 1
    assert result_lower[0] == nodes[1]
    assert len(result_upper) == 1
    assert result_upper[0] == nodes[0]


def test_filter_tag_regex_multiple_tags() -> None:
    """Test filter_tag matches any tag in list."""
    nodes = node_from_org("* DONE Task :foo:bar:baz:\n")

    result = filter_tag(nodes, "^bar$")

    assert len(result) == 1


def test_filter_tag_regex_no_match() -> None:
    """Test filter_tag with no matching tags."""
    nodes = node_from_org("* DONE Task :foo:bar:\n")

    result = filter_tag(nodes, "^baz$")

    assert len(result) == 0


def test_filter_tag_regex_partial_match() -> None:
    """Test filter_tag with partial match."""
    nodes = (
        node_from_org("* DONE Task :foobar:\n")
        + node_from_org("* DONE Task :foo:\n")
        + node_from_org("* DONE Task :barfoo:\n")
    )

    result = filter_tag(nodes, "foo")

    assert len(result) == 3


def test_filter_tag_regex_start_anchor() -> None:
    """Test filter_tag with start anchor."""
    nodes = (
        node_from_org("* DONE Task :testing:\n")
        + node_from_org("* DONE Task :mytesting:\n")
        + node_from_org("* DONE Task :test:\n")
    )

    result = filter_tag(nodes, "^test")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[2]


def test_filter_tag_regex_end_anchor() -> None:
    """Test filter_tag with end anchor."""
    nodes = (
        node_from_org("* DONE Task :testing:\n")
        + node_from_org("* DONE Task :testingmore:\n")
        + node_from_org("* DONE Task :debugging:\n")
    )

    result = filter_tag(nodes, "ing$")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[2]


def test_filter_tag_regex_character_class() -> None:
    """Test filter_tag with character classes."""
    nodes = (
        node_from_org("* DONE Task :test1:\n")
        + node_from_org("* DONE Task :test2:\n")
        + node_from_org("* DONE Task :testa:\n")
    )

    result = filter_tag(nodes, "test[0-9]")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_tag_regex_alternation() -> None:
    """Test filter_tag with alternation (OR)."""
    nodes = (
        node_from_org("* DONE Task :bug:\n")
        + node_from_org("* DONE Task :fix:\n")
        + node_from_org("* DONE Task :feature:\n")
    )

    result = filter_tag(nodes, "bug|fix")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_heading_basic() -> None:
    """Test filter_heading with basic regex patterns."""
    nodes = (
        node_from_org("* DONE Fix bug in parser\n")
        + node_from_org("* DONE Add new feature\n")
        + node_from_org("* DONE Fix typo\n")
    )

    result = filter_heading(nodes, "Fix")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[2]


def test_filter_heading_case_sensitive() -> None:
    """Test filter_heading is case-sensitive."""
    nodes = node_from_org("* DONE Fix Bug\n") + node_from_org("* DONE fix bug\n")

    result_lower = filter_heading(nodes, "fix")
    result_upper = filter_heading(nodes, "Fix")

    assert len(result_lower) == 1
    assert result_lower[0] == nodes[1]
    assert len(result_upper) == 1
    assert result_upper[0] == nodes[0]


def test_filter_heading_word_boundary() -> None:
    """Test filter_heading with word boundaries."""
    nodes = (
        node_from_org("* DONE test the feature\n")
        + node_from_org("* DONE testing feature\n")
        + node_from_org("* DONE test\n")
    )

    result = filter_heading(nodes, r"\btest\b")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[2]


def test_filter_heading_alternation() -> None:
    """Test filter_heading with alternation."""
    nodes = (
        node_from_org("* DONE Fix bug\n")
        + node_from_org("* DONE Resolve issue\n")
        + node_from_org("* DONE Add feature\n")
    )

    result = filter_heading(nodes, "bug|issue")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_heading_no_match() -> None:
    """Test filter_heading with no matching headings."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_heading(nodes, "nonexistent")

    assert len(result) == 0


def test_filter_body_basic() -> None:
    """Test filter_body with basic regex patterns."""
    nodes = (
        node_from_org("* DONE Task\nThis is a test body\n")
        + node_from_org("* DONE Task\nAnother body here\n")
        + node_from_org("* DONE Task\nTest content\n")
    )

    result = filter_body(nodes, "test")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_body_case_sensitive() -> None:
    """Test filter_body is case-sensitive."""
    nodes = node_from_org("* DONE Task\nTest Body\n") + node_from_org("* DONE Task\ntest body\n")

    result_lower = filter_body(nodes, "test")
    result_upper = filter_body(nodes, "Test")

    assert len(result_lower) == 1
    assert result_lower[0] == nodes[1]
    assert len(result_upper) == 1
    assert result_upper[0] == nodes[0]


def test_filter_body_multiline() -> None:
    """Test filter_body with multiline content."""
    org_text = """* DONE Task
First line
Second line
Third line
"""
    nodes = node_from_org(org_text)

    result = filter_body(nodes, "^Second")

    assert len(result) == 1


def test_filter_body_multiline_anchor_end() -> None:
    """Test filter_body with end-of-line anchor."""
    org_text = """* DONE Task
Line one
Line two
Line three
"""
    nodes = node_from_org(org_text)

    result = filter_body(nodes, "two$")

    assert len(result) == 1


def test_filter_body_dot_matches_not_newline() -> None:
    """Test filter_body where dot doesn't match newline."""
    org_text = """* DONE Task
First line
Second line
"""
    nodes = node_from_org(org_text)

    result = filter_body(nodes, "First.*Second")

    assert len(result) == 0


def test_filter_body_alternation() -> None:
    """Test filter_body with alternation."""
    nodes = (
        node_from_org("* DONE Task\nContains TODO\n")
        + node_from_org("* DONE Task\nContains FIXME\n")
        + node_from_org("* DONE Task\nContains nothing\n")
    )

    result = filter_body(nodes, "TODO|FIXME")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_body_no_match() -> None:
    """Test filter_body with no matching bodies."""
    nodes = node_from_org("* DONE Task\nBody content\n")

    result = filter_body(nodes, "nonexistent")

    assert len(result) == 0


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
