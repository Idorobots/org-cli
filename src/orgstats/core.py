"""Core logic for orgstats - Org-mode archive file analysis."""

import typing
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import orgparse


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


@dataclass
class Frequency:  # noqa: PLW1641
    """Represents frequency statistics for a tag/word.

    Attributes:
        total: Total count for this item
    """

    total: int = 0

    def __eq__(self, other: object) -> bool:
        """Compare with another Frequency or int.

        Args:
            other: Object to compare with (Frequency or int)

        Returns:
            True if equal, False otherwise
        """
        if isinstance(other, Frequency):
            return self.total == other.total
        if isinstance(other, int):
            return self.total == other
        return NotImplemented

    def __int__(self) -> int:
        """Convert to int for backward compatibility and comparison.

        Returns:
            The total count as an integer
        """
        return self.total


@dataclass
class Histogram:
    """Represents a distribution of values.

    Attributes:
        values: Dictionary mapping categories to their counts
    """

    values: dict[str, int] = field(default_factory=dict)

    def update(self, key: str, amount: int) -> None:
        """Update the count for a given key by the specified amount.

        Args:
            key: The category to update
            amount: The amount to add
        """
        self.values[key] = self.values.get(key, 0) + amount


@dataclass
class Relations:
    """Represents pair-wise co-occurrence relationships for a tag/word.

    Attributes:
        name: The tag or word name
        relations: Dictionary mapping related tags/words to co-occurrence counts
    """

    name: str
    relations: dict[str, int]


@dataclass
class TimeRange:
    """Represents time range for a tag/word occurrence.

    Attributes:
        earliest: Earliest timestamp this tag/word was encountered
        latest: Latest timestamp this tag/word was encountered
        timeline: Dictionary mapping dates to occurrence counts
    """

    earliest: datetime | None = None
    latest: datetime | None = None
    timeline: dict[date, int] = field(default_factory=dict)

    def __repr__(self) -> str:
        """Return string representation of TimeRange including top day.

        Returns:
            String representation with earliest, latest, and top_day (most intense day).
            Dates are formatted as ISO strings. None values are printed as None.
        """
        top_day = None
        if self.timeline:
            max_count = max(self.timeline.values())
            top_day = min(d for d, count in self.timeline.items() if count == max_count)

        earliest_str = self.earliest.date().isoformat() if self.earliest else None
        latest_str = self.latest.date().isoformat() if self.latest else None
        top_day_str = top_day.isoformat() if top_day else None

        return (
            f"TimeRange(earliest={earliest_str!r}, latest={latest_str!r}, top_day={top_day_str!r})"
        )

    def update(self, timestamp: datetime | date | None) -> None:
        """Update time range with a new timestamp.

        Args:
            timestamp: Timestamp to incorporate into the range (datetime, date, or None)
        """
        if timestamp is None:
            return

        if isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            timestamp = datetime.combine(timestamp, datetime.min.time())

        date_key = timestamp.date()
        self.timeline[date_key] = self.timeline.get(date_key, 0) + 1

        if self.earliest is None or timestamp < self.earliest:
            self.earliest = timestamp
        if self.latest is None or timestamp > self.latest:
            self.latest = timestamp


@dataclass
class Group:
    """Represents a group of related tags (strongly connected component).

    Attributes:
        tags: List of tag names in this group, sorted alphabetically
        time_range: Combined time range for all tags in the group
    """

    tags: list[str]
    time_range: TimeRange


@dataclass
class AnalysisResult:
    """Represents the complete result of analyzing Org-mode nodes.

    Attributes:
        total_tasks: Total number of tasks analyzed
        task_states: Histogram of task states (TODO, DONE, DELEGATED, CANCELLED, SUSPENDED, other)
        task_days: Histogram of DONE task completions by day of week
        timerange: Global time range for all completed (DONE) tasks
        avg_tasks_per_day: Average tasks completed per day (total DONE / days spanned)
        max_single_day_count: Highest number of tasks completed on a single day
        max_repeat_count: Highest number of DONE repeats for any individual task
        tag_frequencies: Dictionary mapping items to their frequency counts
        tag_relations: Dictionary mapping items to their Relations objects
        tag_time_ranges: Dictionary mapping items to their TimeRange objects
        tag_groups: List of tag groups (strongly connected components)

    Note: Despite the 'tag_' prefix, these fields hold data for whichever
    category was analyzed (tags, heading, or body).
    """

    total_tasks: int
    task_states: Histogram
    task_days: Histogram
    timerange: TimeRange
    avg_tasks_per_day: float
    max_single_day_count: int
    max_repeat_count: int
    tag_frequencies: dict[str, Frequency]
    tag_relations: dict[str, Relations]
    tag_time_ranges: dict[str, TimeRange]
    tag_groups: list[Group]


def weekday_to_string(weekday: int) -> str:
    """Map Python weekday integer to capitalized day name.

    Args:
        weekday: Integer from datetime.weekday() (0=Monday, 6=Sunday)

    Returns:
        Capitalized day name (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday)
    """
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[weekday]


def mapped(mapping: dict[str, str], t: str) -> str:
    """Map a tag to its canonical form using the provided mapping.

    Args:
        mapping: Dictionary mapping tags to their canonical forms
        t: Tag to map

    Returns:
        Canonical form if found in mapping, otherwise the original tag
    """
    if t in mapping:
        return mapping[t]
    return t


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


def gamify_exp(node: orgparse.node.OrgNode) -> int | None:
    """Extract gamify_exp value from an org-mode node.

    Args:
        node: Org-mode node to extract gamify_exp from

    Returns:
        Integer value of gamify_exp, or None if not present or invalid
    """
    gamify_exp_raw = node.properties.get("gamify_exp", None)
    gamify_exp_str = str(gamify_exp_raw) if gamify_exp_raw is not None else None
    return parse_gamify_exp(gamify_exp_str)


def normalize(tags: set[str], mapping: dict[str, str]) -> set[str]:
    """Normalize tags by lowercasing, stripping whitespace, removing punctuation,
    and mapping to canonical forms.

    Args:
        tags: Set of tags to normalize
        mapping: Dictionary mapping tags to canonical forms

    Returns:
        Set of normalized and mapped tags
    """
    norm = {
        t.lower()
        .strip()
        .replace(".", "")
        .replace(":", "")
        .replace("!", "")
        .replace(",", "")
        .replace(";", "")
        .replace("?", "")
        for t in tags
    }
    return {mapped(mapping, t) for t in norm}


def _extract_items(node: orgparse.node.OrgNode, mapping: dict[str, str], category: str) -> set[str]:
    """Extract and normalize items from a node based on category.

    Args:
        node: Org-mode node to extract items from
        mapping: Dictionary mapping items to canonical forms
        category: Which datum to extract - "tags", "heading", or "body"

    Returns:
        Set of normalized and mapped items (tags are not normalized, only mapped)
    """
    if category == "tags":
        stripped_tags = {t.strip() for t in node.tags}
        return {mapped(mapping, t) for t in stripped_tags}
    if category == "heading":
        return normalize(set(node.heading.split()), mapping)
    return normalize(set(node.body.split()), mapping)


def _compute_done_count(node: orgparse.node.OrgNode, done_keys: list[str]) -> int:
    """Calculate done count for a node.

    This is max(final, repeats) where:
    - final = 1 if node.todo is in done_keys else 0
    - repeats = count of repeated tasks with after in done_keys

    Args:
        node: Org-mode node
        done_keys: List of completion state keywords

    Returns:
        Count of completed tasks for this node
    """
    final = 1 if node.todo in done_keys else 0
    repeats = len([rt for rt in node.repeated_tasks if rt.after in done_keys])
    return max(final, repeats)


def compute_task_stats(nodes: list[orgparse.node.OrgNode], done_keys: list[str]) -> tuple[int, int]:
    """Compute total task count and maximum repeat count.

    Args:
        nodes: List of org-mode nodes
        done_keys: List of completion state keywords

    Returns:
        Tuple of (total_tasks, max_repeat_count)
    """
    total = 0
    max_repeat_count = 0

    for node in nodes:
        total = total + max(1, len(node.repeated_tasks))

        node_max_repeat = _compute_done_count(node, done_keys)
        max_repeat_count = max(max_repeat_count, node_max_repeat)

    return (total, max_repeat_count)


def compute_max_single_day(timerange: TimeRange) -> int:
    """Get the maximum number of tasks completed on a single day.

    Args:
        timerange: TimeRange object with timeline data

    Returns:
        Maximum count for any single day, or 0 if no timeline data
    """
    if not timerange.timeline:
        return 0
    return max(timerange.timeline.values())


def compute_avg_tasks_per_day(timerange: TimeRange, done_count: int) -> float:
    """Compute average tasks completed per day.

    Args:
        timerange: TimeRange with earliest and latest dates
        done_count: Total number of DONE tasks

    Returns:
        Average tasks per day, or 0.0 if timerange is empty or invalid
    """
    if timerange.earliest is None or timerange.latest is None:
        return 0.0

    days_spanned = (timerange.latest.date() - timerange.earliest.date()).days + 1
    if days_spanned <= 0:
        return 0.0

    return done_count / days_spanned


def compute_task_state_histogram(nodes: list[orgparse.node.OrgNode]) -> Histogram:
    """Compute histogram of task states across all nodes.

    Counts states from repeated tasks if present, otherwise uses node.todo.

    Args:
        nodes: List of org-mode nodes

    Returns:
        Histogram with counts for each task state
    """
    task_states = Histogram(values={})

    for node in nodes:
        if node.repeated_tasks:
            for repeated_task in node.repeated_tasks:
                repeat_state = repeated_task.after or "none"
                task_states.update(repeat_state, 1)
        else:
            node_state = node.todo or "none"
            task_states.update(node_state, 1)

    return task_states


def compute_day_of_week_histogram(
    nodes: list[orgparse.node.OrgNode], done_keys: list[str]
) -> Histogram:
    """Compute histogram of completion days for completed tasks.

    Extracts timestamps from completed tasks and counts by day of week.
    Tasks without timestamps are counted as "unknown".

    Args:
        nodes: List of org-mode nodes
        done_keys: List of completion state keywords

    Returns:
        Histogram with counts for each day of week (Monday-Sunday, unknown)
    """
    task_days = Histogram(values={})

    for node in nodes:
        done_count = _compute_done_count(node, done_keys)

        if done_count > 0:
            timestamps = extract_timestamp(node, done_keys)
            if timestamps:
                for timestamp in timestamps:
                    day_name = weekday_to_string(timestamp.weekday())
                    task_days.update(day_name, 1)
            else:
                task_days.update("unknown", 1)

    return task_days


def compute_global_timerange(nodes: list[orgparse.node.OrgNode], done_keys: list[str]) -> TimeRange:
    """Compute global time range across all completed tasks.

    Extracts timestamps from all completed tasks and builds a unified TimeRange.

    Args:
        nodes: List of org-mode nodes
        done_keys: List of completion state keywords

    Returns:
        TimeRange spanning all completed task timestamps
    """
    global_timerange = TimeRange()

    for node in nodes:
        done_count = _compute_done_count(node, done_keys)

        if done_count > 0:
            timestamps = extract_timestamp(node, done_keys)
            for timestamp in timestamps:
                global_timerange.update(timestamp)

    return global_timerange


def compute_frequencies(
    nodes: list[orgparse.node.OrgNode], mapping: dict[str, str], category: str, done_keys: list[str]
) -> dict[str, Frequency]:
    """Compute frequency statistics for all nodes in a given category.

    For each node, extracts items based on category (tags/heading/body),
    normalizes them, and counts by the node's done count.

    Args:
        nodes: List of org-mode nodes to analyze
        mapping: Dictionary mapping items to canonical forms
        category: Which datum to analyze - "tags", "heading", or "body"
        done_keys: List of completion state keywords

    Returns:
        Dictionary mapping items to their Frequency objects
    """
    frequencies: dict[str, Frequency] = {}

    for node in nodes:
        items = _extract_items(node, mapping, category)
        count = _compute_done_count(node, done_keys)

        if count == 0:
            continue

        for item in items:
            if item not in frequencies:
                frequencies[item] = Frequency()
            frequencies[item].total += count

    return frequencies


def compute_relations(
    nodes: list[orgparse.node.OrgNode], mapping: dict[str, str], category: str, done_keys: list[str]
) -> dict[str, Relations]:
    """Compute pair-wise relations for all nodes in a given category.

    For each node with 2+ items, computes all pair-wise relations
    weighted by the node's done count.

    Args:
        nodes: List of org-mode nodes to analyze
        mapping: Dictionary mapping items to canonical forms
        category: Which datum to analyze - "tags", "heading", or "body"
        done_keys: List of completion state keywords

    Returns:
        Dictionary mapping items to their Relations objects
    """
    relations_dict: dict[str, Relations] = {}

    for node in nodes:
        items = _extract_items(node, mapping, category)
        count = _compute_done_count(node, done_keys)

        if count == 0:
            continue

        items_list = sorted(items)
        for i in range(len(items_list)):
            for j in range(i + 1, len(items_list)):
                item_a = items_list[i]
                item_b = items_list[j]

                if item_a not in relations_dict:
                    relations_dict[item_a] = Relations(name=item_a, relations={})
                if item_b not in relations_dict:
                    relations_dict[item_b] = Relations(name=item_b, relations={})

                relations_dict[item_a].relations[item_b] = (
                    relations_dict[item_a].relations.get(item_b, 0) + count
                )
                relations_dict[item_b].relations[item_a] = (
                    relations_dict[item_b].relations.get(item_a, 0) + count
                )

    return relations_dict


def normalize_timestamp(ts: datetime | date) -> datetime:
    """Normalize all timestamps to use the datetime format

    Args:
        ts: datetime or date

    Returns:
        datetime
    """
    if not isinstance(ts, datetime):
        return datetime.combine(ts, datetime.min.time())
    return ts


def extract_timestamp(node: orgparse.node.OrgNode, done_keys: list[str]) -> list[datetime]:
    """Extract timestamps from a node following priority rules.

    Priority order:
    1. Repeated tasks (all completed tasks)
    2. Closed timestamp
    3. Scheduled timestamp
    4. Deadline timestamp
    5. Datelist (timestamps in body)

    Args:
        node: Org-mode node to extract timestamps from
        done_keys: List of completion state keywords

    Returns:
        List of datetime objects (may be empty if no timestamps found)
    """
    timestamps = []

    if node.repeated_tasks and any(rt.after in done_keys for rt in node.repeated_tasks):
        timestamps.extend([rt.start for rt in node.repeated_tasks if rt.after in done_keys])
    elif node.closed and node.closed.start:
        timestamps.append(node.closed.start)
    elif node.scheduled and node.scheduled.start:
        timestamps.append(node.scheduled.start)
    elif node.deadline and node.deadline.start:
        timestamps.append(node.deadline.start)
    elif node.datelist:
        timestamps.extend([d.start for d in node.datelist if d.start])

    return [normalize_timestamp(t) for t in timestamps]


def extract_timestamp_any(node: orgparse.node.OrgNode) -> list[datetime]:
    """Extract timestamps from a node without filtering by completion state.

    Priority order:
    1. Repeated tasks (all repeated tasks regardless of state)
    2. Closed timestamp
    3. Scheduled timestamp
    4. Deadline timestamp
    5. Datelist (timestamps in body)

    Args:
        node: Org-mode node to extract timestamps from

    Returns:
        List of datetime objects (may be empty if no timestamps found)
    """
    timestamps = []

    if node.repeated_tasks:
        timestamps.extend([rt.start for rt in node.repeated_tasks])
    elif node.closed and node.closed.start:
        timestamps.append(node.closed.start)
    elif node.scheduled and node.scheduled.start:
        timestamps.append(node.scheduled.start)
    elif node.deadline and node.deadline.start:
        timestamps.append(node.deadline.start)
    elif node.datelist:
        timestamps.extend([d.start for d in node.datelist if d.start])

    return [normalize_timestamp(t) for t in timestamps]


def compute_time_ranges(
    nodes: list[orgparse.node.OrgNode], mapping: dict[str, str], category: str, done_keys: list[str]
) -> dict[str, TimeRange]:
    """Compute time ranges for completed tasks in a given category.

    For each completed node, extracts items and timestamps, then builds TimeRange
    objects tracking earliest/latest timestamps and timeline.

    Args:
        nodes: List of org-mode nodes to analyze
        mapping: Dictionary mapping items to canonical forms
        category: Which datum to analyze - "tags", "heading", or "body"
        done_keys: List of completion state keywords

    Returns:
        Dictionary mapping items to their TimeRange objects
    """
    time_ranges: dict[str, TimeRange] = {}

    for node in nodes:
        count = _compute_done_count(node, done_keys)

        if count == 0:
            continue

        items = _extract_items(node, mapping, category)
        timestamps = extract_timestamp(node, done_keys)

        if not timestamps:
            continue

        for item in items:
            if item not in time_ranges:
                time_ranges[item] = TimeRange()

            for timestamp in timestamps:
                time_ranges[item].update(timestamp)

    return time_ranges


def _combine_time_ranges(tag_time_ranges: dict[str, TimeRange], tags: list[str]) -> TimeRange:
    """Combine time ranges from multiple tags into a single TimeRange.

    Args:
        tag_time_ranges: Dictionary mapping tags to their TimeRange objects
        tags: List of tag names to combine

    Returns:
        Combined TimeRange with merged earliest/latest/timeline data
    """
    combined = TimeRange()

    for tag in tags:
        if tag not in tag_time_ranges:
            continue

        time_range = tag_time_ranges[tag]

        if time_range.earliest is not None and (
            combined.earliest is None or time_range.earliest < combined.earliest
        ):
            combined.earliest = time_range.earliest

        if time_range.latest is not None and (
            combined.latest is None or time_range.latest > combined.latest
        ):
            combined.latest = time_range.latest

        for date_key, count in time_range.timeline.items():
            combined.timeline[date_key] = combined.timeline.get(date_key, 0) + count

    return combined


def compute_groups(
    relations: dict[str, Relations], max_relations: int, tag_time_ranges: dict[str, TimeRange]
) -> list[Group]:
    """Compute strongly connected components from tag relations using Tarjan's algorithm.

    Args:
        relations: Dictionary mapping tags to their Relations objects
        max_relations: Maximum number of relations to consider per tag
        tag_time_ranges: Dictionary mapping tags to their TimeRange objects

    Returns:
        List of Group objects representing strongly connected components
    """
    if not relations:
        return []

    graph: dict[str, list[str]] = {}
    for tag, rel_obj in relations.items():
        sorted_relations = sorted(rel_obj.relations.items(), key=lambda x: -x[1])
        top_relations = sorted_relations[:max_relations]
        graph[tag] = [rel_name for rel_name, _ in top_relations]

    index_counter = [0]
    stack: list[str] = []
    lowlinks: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        for successor in graph.get(node, []):
            if successor not in index:
                strongconnect(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif on_stack.get(successor, False):
                lowlinks[node] = min(lowlinks[node], index[successor])

        if lowlinks[node] == index[node]:
            component: list[str] = []
            while True:
                successor = stack.pop()
                on_stack[successor] = False
                component.append(successor)
                if successor == node:
                    break
            sccs.append(component)

    for node in graph:
        if node not in index:
            strongconnect(node)

    return [
        Group(tags=sorted(scc), time_range=_combine_time_ranges(tag_time_ranges, scc))
        for scc in sccs
    ]


def analyze(
    nodes: list[orgparse.node.OrgNode],
    mapping: dict[str, str],
    category: str,
    max_relations: int,
    done_keys: list[str],
) -> AnalysisResult:
    """Analyze org-mode nodes and extract task statistics.

    Args:
        nodes: List of org-mode nodes from orgparse
        mapping: Dictionary mapping tags to canonical forms
        category: Which datum to analyze - "tags", "heading", or "body"
        max_relations: Maximum number of relations to consider for grouping
        done_keys: List of completion state keywords

    Returns:
        AnalysisResult containing task counts and frequency dictionaries for the selected category
    """
    tag_frequencies = compute_frequencies(nodes, mapping, category, done_keys)
    tag_relations = compute_relations(nodes, mapping, category, done_keys)
    tag_time_ranges = compute_time_ranges(nodes, mapping, category, done_keys)
    tag_groups = compute_groups(tag_relations, max_relations, tag_time_ranges)
    task_states = compute_task_state_histogram(nodes)
    task_days = compute_day_of_week_histogram(nodes, done_keys)
    global_timerange = compute_global_timerange(nodes, done_keys)
    total, max_repeat_count = compute_task_stats(nodes, done_keys)
    max_single_day = compute_max_single_day(global_timerange)
    done_count = sum(task_states.values.get(key, 0) for key in done_keys)
    avg_tasks_per_day = compute_avg_tasks_per_day(global_timerange, done_count)

    return AnalysisResult(
        total_tasks=total,
        task_states=task_states,
        task_days=task_days,
        timerange=global_timerange,
        avg_tasks_per_day=avg_tasks_per_day,
        max_single_day_count=max_single_day,
        max_repeat_count=max_repeat_count,
        tag_frequencies=tag_frequencies,
        tag_relations=tag_relations,
        tag_time_ranges=tag_time_ranges,
        tag_groups=tag_groups,
    )


def clean(disallowed: set[str], tags: dict[str, Frequency]) -> dict[str, Frequency]:
    """Remove tags from the disallowed set (stop words).

    Args:
        disallowed: Set of tags to filter out (stop words, lowercase)
        tags: Dictionary of tag frequencies

    Returns:
        Dictionary with disallowed tags removed (case-insensitive comparison)
    """
    disallowed_lower = {d.lower() for d in disallowed}
    return {t: tags[t] for t in tags if t.lower() not in disallowed_lower}


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

    # NOTE: Performance optimization to avoid deep copying and mutating the original node
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
    return [node for node in nodes if (gamify_exp(node) or 10) > threshold]


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
    return [node for node in nodes if (gamify_exp(node) or 10) < threshold]


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


def filter_tag(nodes: list[orgparse.node.OrgNode], tag_name: str) -> list[orgparse.node.OrgNode]:
    """Filter nodes with exact tag match (case-sensitive).

    Matches against individual tags in node.tags list.
    Nodes without the tag are excluded.

    Args:
        nodes: List of org-mode nodes to filter
        tag_name: Tag name to match

    Returns:
        Filtered list of nodes
    """
    return [node for node in nodes if tag_name in node.tags]


def filter_completed(
    nodes: list[orgparse.node.OrgNode], done_keys: list[str]
) -> list[orgparse.node.OrgNode]:
    """Filter nodes with todo state in done_keys.

    For nodes with repeated tasks, filters the repeated_tasks list to only include
    tasks with after state in done_keys. For nodes without repeated tasks,
    checks node.todo.

    Args:
        nodes: List of org-mode nodes to filter
        done_keys: List of completion state keywords

    Returns:
        Filtered list of nodes (some may be deep copies with filtered repeated_tasks)
    """
    result = []

    for node in nodes:
        if node.repeated_tasks:
            filtered_node = _filter_node_repeats(node, lambda rt: rt.after in done_keys)
            if filtered_node is not None:
                result.append(filtered_node)
        elif node.todo in done_keys:
            result.append(node)

    return result


def filter_not_completed(
    nodes: list[orgparse.node.OrgNode], todo_keys: list[str]
) -> list[orgparse.node.OrgNode]:
    """Filter nodes with todo state in todo_keys.

    For nodes with repeated tasks, filters the repeated_tasks list to only include
    tasks with after state in todo_keys. For nodes without repeated tasks,
    checks node.todo.

    Args:
        nodes: List of org-mode nodes to filter
        todo_keys: List of TODO state keywords

    Returns:
        Filtered list of nodes (some may be deep copies with filtered repeated_tasks)
    """
    result = []

    for node in nodes:
        if node.repeated_tasks:
            filtered_node = _filter_node_repeats(node, lambda rt: rt.after in todo_keys)
            if filtered_node is not None:
                result.append(filtered_node)
        elif node.todo in todo_keys:
            result.append(node)

    return result


def expand_timeline(timeline: dict[date, int], earliest: date, latest: date) -> dict[date, int]:
    """Fill in missing dates with 0 activity to create a complete timeline.

    Args:
        timeline: Sparse timeline with only days that have activity
        earliest: First date in the range
        latest: Last date in the range

    Returns:
        Complete timeline with all dates from earliest to latest, missing dates set to 0
    """
    expanded: dict[date, int] = {}
    current = earliest

    while current <= latest:
        expanded[current] = timeline.get(current, 0)
        current = current + timedelta(days=1)

    return expanded


def bucket_timeline(timeline: dict[date, int], num_buckets: int) -> list[int]:
    """Group timeline into N equal-sized time buckets and sum activity per bucket.

    Args:
        timeline: Complete timeline dict mapping dates to activity counts
        num_buckets: Number of buckets to create

    Returns:
        List of bucket sums (length = num_buckets)
    """
    if not timeline:
        return [0] * num_buckets

    sorted_dates = sorted(timeline.keys())
    total_days = len(sorted_dates)

    if total_days == 0:
        return [0] * num_buckets

    buckets = [0] * num_buckets

    for i, current_date in enumerate(sorted_dates):
        bucket_index = (i * num_buckets) // total_days
        if bucket_index >= num_buckets:
            bucket_index = num_buckets - 1
        buckets[bucket_index] += timeline[current_date]

    return buckets


def _map_value_to_bar(value: int, max_value: int) -> str:
    """Map a value to appropriate unicode bar character based on percentage.

    Args:
        value: Value to map
        max_value: Maximum value for percentage calculation

    Returns:
        Unicode bar character representing the percentage
    """
    if max_value == 0 or value == 0:
        return " "

    percentage = (value / max_value) * 100
    thresholds = [
        (100, "█"),
        (87.5, "▇"),
        (75, "▆"),
        (62.5, "▅"),
        (50, "▄"),
        (37.5, "▃"),
        (25, "▂"),
    ]

    for threshold, char in thresholds:
        if percentage >= threshold:
            return char
    return "▁"


def render_histogram(
    histogram: Histogram, total_blocks: int, category_order: list[str] | None
) -> list[str]:
    """Render histogram as visual bar chart.

    Args:
        histogram: Histogram object to render
        total_blocks: Number of blocks for 100% width (e.g., args.buckets)
        category_order: Optional list specifying display order of categories

    Returns:
        List of formatted strings, one per category
    """
    total_sum = sum(histogram.values.values())
    categories = category_order if category_order is not None else sorted(histogram.values.keys())

    lines = []
    for category in categories:
        value = histogram.values.get(category, 0)
        display_name = category[:8] + "." if len(category) > 9 else category
        bar_length = int((value / total_sum) * total_blocks) if total_sum > 0 else 0
        bars = "█" * bar_length
        line = f"{display_name:9s}┊{bars} {value}"
        lines.append(line)

    return lines


def render_timeline_chart(
    timeline: dict[date, int], earliest: date, latest: date, num_buckets: int
) -> tuple[str, str, str]:
    """Create ASCII bar chart from timeline data.

    Args:
        timeline: Timeline dict mapping dates to activity counts
        earliest: First date in the range
        latest: Last date in the range
        num_buckets: Number of buckets (bars) in the chart

    Returns:
        Tuple of (date_line, chart_line, underline)
    """
    expanded = expand_timeline(timeline, earliest, latest)
    buckets = bucket_timeline(expanded, num_buckets)
    max_value = max(buckets) if buckets else 0

    bars = "".join(_map_value_to_bar(value, max_value) for value in buckets)

    start_date_str = earliest.isoformat()
    end_date_str = latest.isoformat()

    chart_width = len(bars) + 2
    padding_spaces = chart_width - len(start_date_str) - len(end_date_str)
    date_padding = " " * max(0, padding_spaces)
    date_line = f"{start_date_str}{date_padding}{end_date_str}"

    if timeline:
        max_count = max(timeline.values())
        top_day = min(d for d, count in timeline.items() if count == max_count)
        top_day_str = f"{max_count} ({top_day.isoformat()})"
    else:
        top_day_str = "0"

    chart_line = f"┊{bars}┊ {top_day_str}"

    underline = "‾" * chart_width

    return (date_line, chart_line, underline)
