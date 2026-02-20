"""Node filtering functions."""

import re
import typing
from collections.abc import Callable
from datetime import datetime

import orgparse

from orgstats.timestamp import extract_timestamp_any


class _FilteredOrgNode(orgparse.node.OrgNode):
    """Wrapper for OrgNode that overrides repeated_tasks without copying the entire node.

    This class delegates all attribute access to the original node except for repeated_tasks,
    which is replaced with a filtered list. This avoids the performance cost of deep copying.
    """

    def __init__(
        self,
        original_node: orgparse.node.OrgNode,
        filtered_repeats: list[orgparse.date.OrgDateRepeatedTask],
    ) -> None:
        """Initialize with original node and filtered repeated tasks.

        Args:
            original_node: The original OrgNode to wrap
            filtered_repeats: The filtered list of repeated tasks
        """
        self._original_node = original_node
        self._filtered_repeats = filtered_repeats

    @property
    def repeated_tasks(self) -> list[orgparse.date.OrgDateRepeatedTask]:
        """Return the filtered repeated tasks.

        Returns:
            Filtered list of repeated tasks
        """
        return self._filtered_repeats

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        """Delegate attribute access to the original node.

        Args:
            name: Attribute name

        Returns:
            Attribute value from original node
        """
        return getattr(self._original_node, name)


def parse_gamify_exp(gamify_exp_value: str | None) -> int | None:
    """Parse gamify_exp property and return the numeric value.

    Args:
        gamify_exp_value: The gamify_exp property value (string or None)

    Returns:
        Integer value if parseable, None if missing or invalid

    Rules:
    - If None or empty: return None (default to regular)
    - If integer string: return that integer
    - If "(X Y)" format: return X
    - Otherwise: return None (default to regular)
    """
    if gamify_exp_value is None or gamify_exp_value.strip() == "":
        return None

    value = gamify_exp_value.strip()

    try:
        return int(value)
    except ValueError:
        pass

    if value.startswith("(") and value.endswith(")"):
        inner = value[1:-1].strip()
        parts = inner.split()
        if len(parts) >= 2:
            try:
                return int(parts[0])
            except ValueError:
                pass

    return None


def get_gamify_exp(node: orgparse.node.OrgNode) -> int | None:
    """Extract gamify_exp value from an org-mode node.

    Args:
        node: Org-mode node to extract gamify_exp from

    Returns:
        Integer value of gamify_exp, or None if not present or invalid
    """
    gamify_exp_raw = node.properties.get("gamify_exp", None)
    gamify_exp_str = str(gamify_exp_raw) if gamify_exp_raw is not None else None
    return parse_gamify_exp(gamify_exp_str)


def get_gamify_category(node: orgparse.node.OrgNode) -> str:
    """Extract gamify_exp value from an org-mode node and decide what category it belongs to.

    Args:
        node: Org-mode node to extract gamify_exp from

    Returns:
        String representing the category
    """

    exp_value = get_gamify_exp(node)

    if exp_value is None:
        return "regular"
    if exp_value < 10:
        return "simple"
    if exp_value < 20:
        return "regular"
    return "hard"


def get_repeat_count(node: orgparse.node.OrgNode) -> int:
    """Get total repeat count for a node.

    Returns max(1, len(node.repeated_tasks))

    Args:
        node: Org-mode node

    Returns:
        Repeat count (minimum 1)
    """
    return max(1, len(node.repeated_tasks))


def _filter_node_repeats(
    node: orgparse.node.OrgNode, predicate: Callable[[orgparse.date.OrgDateRepeatedTask], bool]
) -> orgparse.node.OrgNode | None:
    """Filter repeated tasks in a node based on a predicate function.

    Args:
        node: Org-mode node to filter
        predicate: Function that takes a repeated task and returns True if it should be kept

    Returns:
        - Original node if all repeats match (or no repeats)
        - FilteredOrgNode with filtered repeated_tasks if some match
        - None if no repeats match (and node doesn't have valid non-repeat data)
    """
    if not node.repeated_tasks:
        return node

    matching_repeats = [rt for rt in node.repeated_tasks if predicate(rt)]

    if len(matching_repeats) == len(node.repeated_tasks):
        return node

    if len(matching_repeats) == 0:
        return None

    return _FilteredOrgNode(node, matching_repeats)


def filter_gamify_exp_above(
    nodes: list[orgparse.node.OrgNode], threshold: int
) -> list[orgparse.node.OrgNode]:
    """Filter nodes where gamify_exp > threshold (non-inclusive).

    Missing gamify_exp defaults to 10.

    Args:
        nodes: List of org-mode nodes to filter
        threshold: Threshold value

    Returns:
        Filtered list of nodes
    """
    return [node for node in nodes if (get_gamify_exp(node) or 10) > threshold]


def filter_gamify_exp_below(
    nodes: list[orgparse.node.OrgNode], threshold: int
) -> list[orgparse.node.OrgNode]:
    """Filter nodes where gamify_exp < threshold (non-inclusive).

    Missing gamify_exp defaults to 10.

    Args:
        nodes: List of org-mode nodes to filter
        threshold: Threshold value

    Returns:
        Filtered list of nodes
    """
    return [node for node in nodes if (get_gamify_exp(node) or 10) < threshold]


def filter_repeats_above(
    nodes: list[orgparse.node.OrgNode], threshold: int
) -> list[orgparse.node.OrgNode]:
    """Filter nodes where repeat count > threshold (non-inclusive).

    Repeat count = max(1, len(node.repeated_tasks))

    Args:
        nodes: List of org-mode nodes to filter
        threshold: Threshold value

    Returns:
        Filtered list of nodes
    """
    return [node for node in nodes if get_repeat_count(node) > threshold]


def filter_repeats_below(
    nodes: list[orgparse.node.OrgNode], threshold: int
) -> list[orgparse.node.OrgNode]:
    """Filter nodes where repeat count < threshold (non-inclusive).

    Repeat count = max(1, len(node.repeated_tasks))

    Args:
        nodes: List of org-mode nodes to filter
        threshold: Threshold value

    Returns:
        Filtered list of nodes
    """
    return [node for node in nodes if get_repeat_count(node) < threshold]


def filter_date_from(
    nodes: list[orgparse.node.OrgNode], date_threshold: datetime
) -> list[orgparse.node.OrgNode]:
    """Filter nodes with any timestamp after date_threshold (inclusive).

    For nodes with repeated tasks, filters the repeated_tasks list to only include
    tasks with timestamps >= date_threshold. For nodes without repeated tasks,
    checks the node's timestamp.

    Uses extract_timestamp_any() logic. Nodes without timestamps are excluded.

    Args:
        nodes: List of org-mode nodes to filter
        date_threshold: Date threshold (inclusive)

    Returns:
        Filtered list of nodes (some may be deep copies with filtered repeated_tasks)
    """
    result = []

    for node in nodes:
        if node.repeated_tasks:
            filtered_node = _filter_node_repeats(node, lambda rt: rt.start >= date_threshold)
            if filtered_node is not None:
                result.append(filtered_node)
        else:
            timestamps = extract_timestamp_any(node)
            if any(timestamp >= date_threshold for timestamp in timestamps):
                result.append(node)

    return result


def filter_date_until(
    nodes: list[orgparse.node.OrgNode], date_threshold: datetime
) -> list[orgparse.node.OrgNode]:
    """Filter nodes with any timestamp before date_threshold (inclusive).

    For nodes with repeated tasks, filters the repeated_tasks list to only include
    tasks with timestamps <= date_threshold. For nodes without repeated tasks,
    checks the node's timestamp.

    Uses extract_timestamp_any() logic. Nodes without timestamps are excluded.

    Args:
        nodes: List of org-mode nodes to filter
        date_threshold: Date threshold (inclusive)

    Returns:
        Filtered list of nodes (some may be deep copies with filtered repeated_tasks)
    """
    result = []

    for node in nodes:
        if node.repeated_tasks:
            filtered_node = _filter_node_repeats(node, lambda rt: rt.start <= date_threshold)
            if filtered_node is not None:
                result.append(filtered_node)
        else:
            timestamps = extract_timestamp_any(node)
            if any(timestamp <= date_threshold for timestamp in timestamps):
                result.append(node)

    return result


def filter_property(
    nodes: list[orgparse.node.OrgNode], property_name: str, property_value: str
) -> list[orgparse.node.OrgNode]:
    """Filter nodes with exact property match (case-sensitive).

    Nodes without the property are excluded.
    For gamify_exp property, nodes without it are NOT treated as having value 10.

    Args:
        nodes: List of org-mode nodes to filter
        property_name: Property name to match
        property_value: Property value to match

    Returns:
        Filtered list of nodes
    """
    return [
        node
        for node in nodes
        if (prop_value := node.properties.get(property_name, None)) is not None
        and str(prop_value) == property_value
    ]


def filter_tag(nodes: list[orgparse.node.OrgNode], tag_pattern: str) -> list[orgparse.node.OrgNode]:
    """Filter nodes where any tag matches the regex pattern (case-sensitive).

    Matches against individual tags in node.tags list using regex.
    Nodes without any matching tag are excluded.

    Args:
        nodes: List of org-mode nodes to filter
        tag_pattern: Regex pattern to match against tags

    Returns:
        Filtered list of nodes

    Raises:
        re.error: If tag_pattern is not a valid regex
    """
    pattern = re.compile(tag_pattern)
    return [node for node in nodes if any(pattern.search(tag) for tag in node.tags)]


def _make_completion_predicate(
    keys: list[str],
) -> Callable[[orgparse.date.OrgDateRepeatedTask], bool]:
    """Create a predicate function for checking completed status.

    Args:
        keys: List of state keywords

    Returns:
        Predicate function
    """

    def predicate(rt: orgparse.date.OrgDateRepeatedTask) -> bool:
        return rt.after in keys

    return predicate


def _make_not_completion_predicate(
    keys: list[str],
) -> Callable[[orgparse.date.OrgDateRepeatedTask], bool]:
    """Create a predicate function for checking not-completed status.

    Includes tasks with state in keys OR without a state.

    Args:
        keys: List of state keywords

    Returns:
        Predicate function
    """

    def predicate(rt: orgparse.date.OrgDateRepeatedTask) -> bool:
        return rt.after in keys or not rt.after

    return predicate


def filter_completed(nodes: list[orgparse.node.OrgNode]) -> list[orgparse.node.OrgNode]:
    """Filter nodes with todo state in node.env.done_keys.

    For nodes with repeated tasks, filters the repeated_tasks list to only include
    tasks with after state in the node's environment done_keys. For nodes without
    repeated tasks, checks node.todo against node.env.done_keys.

    Args:
        nodes: List of org-mode nodes to filter

    Returns:
        Filtered list of nodes (some may be deep copies with filtered repeated_tasks)
    """
    result = []

    for node in nodes:
        done_keys = node.env.done_keys
        if node.repeated_tasks:
            filtered_node = _filter_node_repeats(node, _make_completion_predicate(done_keys))
            if filtered_node is not None:
                result.append(filtered_node)
        elif node.todo in done_keys:
            result.append(node)

    return result


def filter_not_completed(nodes: list[orgparse.node.OrgNode]) -> list[orgparse.node.OrgNode]:
    """Filter nodes with todo state in node.env.todo_keys or without a todo state.

    For nodes with repeated tasks, filters the repeated_tasks list to only include
    tasks with after state in the node's environment todo_keys or without a state.
    For nodes without repeated tasks, checks node.todo against node.env.todo_keys
    or includes nodes without a todo state.

    Args:
        nodes: List of org-mode nodes to filter

    Returns:
        Filtered list of nodes (some may be deep copies with filtered repeated_tasks)
    """
    result = []

    for node in nodes:
        todo_keys = node.env.todo_keys if hasattr(node, "env") else []
        if node.repeated_tasks:
            filtered_node = _filter_node_repeats(node, _make_not_completion_predicate(todo_keys))
            if filtered_node is not None:
                result.append(filtered_node)
        elif node.todo in todo_keys or not node.todo:
            result.append(node)

    return result


def filter_heading(
    nodes: list[orgparse.node.OrgNode], heading_pattern: str
) -> list[orgparse.node.OrgNode]:
    """Filter nodes where heading matches the regex pattern (case-sensitive).

    Args:
        nodes: List of org-mode nodes to filter
        heading_pattern: Regex pattern to match against heading

    Returns:
        Filtered list of nodes

    Raises:
        re.error: If heading_pattern is not a valid regex
    """
    pattern = re.compile(heading_pattern)
    return [node for node in nodes if node.heading and pattern.search(node.heading)]


def filter_body(
    nodes: list[orgparse.node.OrgNode], body_pattern: str
) -> list[orgparse.node.OrgNode]:
    """Filter nodes where body text matches the regex pattern (case-sensitive, multiline).

    Uses re.MULTILINE flag for pattern matching.

    Args:
        nodes: List of org-mode nodes to filter
        body_pattern: Regex pattern to match against body text

    Returns:
        Filtered list of nodes

    Raises:
        re.error: If body_pattern is not a valid regex
    """
    pattern = re.compile(body_pattern, re.MULTILINE)
    return [node for node in nodes if node.body and pattern.search(node.body)]
