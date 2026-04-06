"""Node filtering functions."""

import re
from collections.abc import Callable
from datetime import datetime

from org_parser.document import Heading
from org_parser.element import Repeat

from org.timestamp import extract_timestamp_any


def get_repeat_count(node: Heading) -> int:
    """Get total repeat count for a node."""
    return max(1, len(node.repeats))


def _filter_node_repeats(node: Heading, predicate: Callable[[Repeat], bool]) -> Heading | None:
    """Filter repeated tasks in place based on a predicate function."""
    if not node.repeats:
        return node

    matching_repeats = [repeat for repeat in node.repeats if predicate(repeat)]
    if len(matching_repeats) == len(node.repeats):
        return node
    if not matching_repeats:
        return None

    node.repeats = matching_repeats
    return node


def filter_repeats_above(nodes: list[Heading], threshold: int) -> list[Heading]:
    """Filter nodes where repeat count > threshold (non-inclusive)."""
    return [node for node in nodes if get_repeat_count(node) > threshold]


def filter_repeats_below(nodes: list[Heading], threshold: int) -> list[Heading]:
    """Filter nodes where repeat count < threshold (non-inclusive)."""
    return [node for node in nodes if get_repeat_count(node) < threshold]


def filter_date_from(nodes: list[Heading], date_threshold: datetime) -> list[Heading]:
    """Filter nodes with any timestamp after date_threshold (inclusive)."""
    result: list[Heading] = []
    for node in nodes:
        if node.repeats:
            filtered_node = _filter_node_repeats(
                node,
                lambda repeat: repeat.timestamp.start >= date_threshold,
            )
            if filtered_node is not None:
                result.append(filtered_node)
            continue

        timestamps = extract_timestamp_any(node)
        if any(timestamp >= date_threshold for timestamp in timestamps):
            result.append(node)
    return result


def filter_date_until(nodes: list[Heading], date_threshold: datetime) -> list[Heading]:
    """Filter nodes with any timestamp before date_threshold (inclusive)."""
    result: list[Heading] = []
    for node in nodes:
        if node.repeats:
            filtered_node = _filter_node_repeats(
                node,
                lambda repeat: repeat.timestamp.start <= date_threshold,
            )
            if filtered_node is not None:
                result.append(filtered_node)
            continue

        timestamps = extract_timestamp_any(node)
        if any(timestamp <= date_threshold for timestamp in timestamps):
            result.append(node)
    return result


def filter_property(nodes: list[Heading], property_name: str, property_value: str) -> list[Heading]:
    """Filter nodes with exact property match (case-sensitive)."""
    return [
        node
        for node in nodes
        if (prop_value := node.properties.get(property_name, None)) is not None
        and str(prop_value) == property_value
    ]


def filter_tag(nodes: list[Heading], tag_pattern: str) -> list[Heading]:
    """Filter nodes where any tag matches the regex pattern (case-sensitive)."""
    pattern = re.compile(tag_pattern)
    return [node for node in nodes if any(pattern.search(tag) for tag in node.tags)]


def _make_completion_predicate(keys: list[str]) -> Callable[[Repeat], bool]:
    """Create predicate for completed repeat states."""

    def predicate(repeat: Repeat) -> bool:
        return repeat.after in keys

    return predicate


def _make_not_completion_predicate(keys: list[str]) -> Callable[[Repeat], bool]:
    """Create predicate for non-completed repeat states."""

    def predicate(repeat: Repeat) -> bool:
        return repeat.after in keys or not repeat.after

    return predicate


def filter_completed(nodes: list[Heading]) -> list[Heading]:
    """Filter nodes with todo state in document done states."""
    result: list[Heading] = []
    for node in nodes:
        done_states = node.document.done_states
        if node.repeats:
            filtered_node = _filter_node_repeats(node, _make_completion_predicate(done_states))
            if filtered_node is not None:
                result.append(filtered_node)
            continue
        if node.is_completed:
            result.append(node)
    return result


def filter_not_completed(nodes: list[Heading]) -> list[Heading]:
    """Filter nodes with todo state in document todo states or without a todo state."""
    result: list[Heading] = []
    for node in nodes:
        todo_states = node.document.todo_states
        if node.repeats:
            filtered_node = _filter_node_repeats(node, _make_not_completion_predicate(todo_states))
            if filtered_node is not None:
                result.append(filtered_node)
            continue
        if not node.is_completed:
            result.append(node)
    return result


def filter_heading(nodes: list[Heading], heading_pattern: str) -> list[Heading]:
    """Filter nodes where title_text matches the regex pattern (case-sensitive)."""
    pattern = re.compile(heading_pattern)
    return [node for node in nodes if node.title_text and pattern.search(node.title_text)]


def filter_body(nodes: list[Heading], body_pattern: str) -> list[Heading]:
    """Filter nodes where body text matches the regex pattern (case-sensitive, multiline)."""
    pattern = re.compile(body_pattern, re.MULTILINE)
    return [node for node in nodes if node.body_text and pattern.search(node.body_text)]


def filter_category(nodes: list[Heading], category_value: str) -> list[Heading]:
    """Filter nodes by effective heading category value."""
    return [
        node
        for node in nodes
        if category_value
        == ("null" if node.category is None or str(node.category) == "" else str(node.category))
    ]


def preprocess_tags_as_category(nodes: list[Heading]) -> list[Heading]:
    """Set heading category to the first effective tag when present."""
    for node in nodes:
        if node.tags:
            node.heading_category = node.heading_tags[0]
    return nodes
