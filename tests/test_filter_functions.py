"""Unit tests for individual filter functions."""

from datetime import date

import orgparse

from orgstats.core import (
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_gamify_exp_above,
    filter_gamify_exp_below,
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

    result = filter_date_from(nodes, date(2025, 1, 31), ["DONE"])

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_filter_date_from_boundary() -> None:
    """Test filter_date_from with boundary date (non-inclusive)."""
    org_text = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    nodes = node_from_org(org_text)

    result = filter_date_from(nodes, date(2025, 1, 15), ["DONE"])

    assert len(result) == 0


def test_filter_date_from_no_timestamp() -> None:
    """Test filter_date_from excludes nodes without timestamps."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_date_from(nodes, date(2025, 1, 1), ["DONE"])

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

    result = filter_date_from(nodes, date(2025, 2, 1), ["DONE"])

    assert len(result) == 1


def test_filter_date_until_basic() -> None:
    """Test filter_date_until with basic date filtering."""
    org_text_jan = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    org_text_feb = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"

    nodes = node_from_org(org_text_jan) + node_from_org(org_text_feb)

    result = filter_date_until(nodes, date(2025, 2, 1), ["DONE"])

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_filter_date_until_boundary() -> None:
    """Test filter_date_until with boundary date (non-inclusive)."""
    org_text = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    nodes = node_from_org(org_text)

    result = filter_date_until(nodes, date(2025, 1, 15), ["DONE"])

    assert len(result) == 0


def test_filter_date_until_no_timestamp() -> None:
    """Test filter_date_until excludes nodes without timestamps."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_date_until(nodes, date(2025, 12, 31), ["DONE"])

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


def test_filter_completed_basic() -> None:
    """Test filter_completed with basic completion filtering."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* TODO Task\n")
        + node_from_org("* DONE Another\n")
    )

    result = filter_completed(nodes, ["DONE"])

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[2]


def test_filter_completed_multiple_done_keys() -> None:
    """Test filter_completed with multiple done keys."""
    nodes = node_from_org(
        "* DONE Task\n", todo_keys=["TODO"], done_keys=["DONE", "DELEGATED"]
    ) + node_from_org("* DELEGATED Task\n", todo_keys=["TODO"], done_keys=["DONE", "DELEGATED"])

    result = filter_completed(nodes, ["DONE", "DELEGATED"])

    assert len(result) == 2


def test_filter_completed_no_match() -> None:
    """Test filter_completed with no matching nodes."""
    nodes = node_from_org("* TODO Task\n")

    result = filter_completed(nodes, ["DONE"])

    assert len(result) == 0


def test_filter_not_completed_basic() -> None:
    """Test filter_not_completed with basic filtering."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* TODO Task\n")
        + node_from_org("* TODO Another\n")
    )

    result = filter_not_completed(nodes, ["TODO"])

    assert len(result) == 2
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]


def test_filter_not_completed_multiple_todo_keys() -> None:
    """Test filter_not_completed with multiple todo keys."""
    nodes = node_from_org(
        "* TODO Task\n", todo_keys=["TODO", "WAITING"], done_keys=["DONE"]
    ) + node_from_org("* WAITING Task\n", todo_keys=["TODO", "WAITING"], done_keys=["DONE"])

    result = filter_not_completed(nodes, ["TODO", "WAITING"])

    assert len(result) == 2


def test_filter_not_completed_no_match() -> None:
    """Test filter_not_completed with no matching nodes."""
    nodes = node_from_org("* DONE Task\n")

    result = filter_not_completed(nodes, ["TODO"])

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
