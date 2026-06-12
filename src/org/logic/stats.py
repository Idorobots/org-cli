"""Core analysis logic and data structures."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from org.logic.time import extract_timestamp_any
from org.logic.validation import parse_group_values


if TYPE_CHECKING:
    from org_parser.document import Heading


@dataclass
class Frequency:  # noqa: PLW1641
    """Represents frequency statistics for a tag/word."""

    total: int = 0

    def __eq__(self, other: object) -> bool:
        """Compare with another Frequency or int."""
        if isinstance(other, Frequency):
            return self.total == other.total
        if isinstance(other, int):
            return self.total == other
        return NotImplemented

    def __int__(self) -> int:
        """Convert to int for backward compatibility and comparison."""
        return self.total


@dataclass
class TimeRange:
    """Represents time range for a tag/word occurrence."""

    earliest: datetime | None = None
    latest: datetime | None = None
    timeline: dict[date, int] = field(default_factory=dict)

    def __repr__(self) -> str:
        """Return string representation of TimeRange including top day."""
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
        """Update time range with a new timestamp."""
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
class Relations:
    """Represents pair-wise co-occurrence relationships for a tag/word."""

    name: str
    relations: dict[str, int]


@dataclass
class Distribution:
    """Represents a distribution of values."""

    values: dict[str, int] = field(default_factory=dict)

    def update(self, key: str, amount: int) -> None:
        """Update the count for a given key by the specified amount."""
        self.values[key] = self.values.get(key, 0) + amount


@dataclass
class Tag:
    """Represents complete statistics for a single tag."""

    name: str
    total_tasks: int
    avg_tasks_per_day: float
    max_single_day_count: int
    relations: dict[str, int]
    time_range: TimeRange


@dataclass
class Group:
    """Represents a group of related tags (strongly connected component)."""

    tags: list[str]
    time_range: TimeRange
    total_tasks: int
    avg_tasks_per_day: float
    max_single_day_count: int


@dataclass
class AnalysisResult:
    """Represents the complete result of analyzing Org-mode nodes."""

    total_tasks: int
    unique_tasks: int
    task_states: Distribution
    task_categories: Distribution
    task_priorities: Distribution
    task_days: Distribution
    timerange: TimeRange
    avg_tasks_per_day: float
    max_single_day_count: int
    max_repeat_count: int
    tags: dict[str, Tag]
    tag_groups: list[Group]


def get_top_day_info(time_range: TimeRange | None) -> tuple[str, int] | None:
    """Extract top day and its count from TimeRange."""
    if not time_range or not time_range.timeline:
        return None
    max_count = max(time_range.timeline.values())
    top_day = min(d for d, count in time_range.timeline.items() if count == max_count)
    return (top_day.isoformat(), max_count)


def weekday_to_string(weekday: int) -> str:
    """Map Python weekday integer to capitalized day name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[weekday]


def mapped(mapping: dict[str, str], t: str) -> str:
    """Map a tag to its canonical form using the provided mapping."""
    if t in mapping:
        return mapping[t]
    return t


def normalize(tags: set[str], mapping: dict[str, str]) -> set[str]:
    """Normalize tags by lowercasing, stripping whitespace, removing punctuation."""
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


def _extract_items(node: Heading, mapping: dict[str, str], category: str) -> set[str]:
    """Extract and normalize items from a node based on category."""
    if category == "tags":
        stripped_tags = {t.strip() for t in node.tags}
        return {mapped(mapping, t) for t in stripped_tags}
    if category == "heading":
        return normalize(set(node.title_text.split()), mapping)
    return normalize(set(node.body_text.split()), mapping)


def compute_task_stats(nodes: list[Heading]) -> tuple[int, int]:
    """Compute total task count and maximum repeat count."""
    total = 0
    max_repeat_count = 0

    for node in nodes:
        total = total + max(1, len(node.repeats))
        max_repeat_count = max(max_repeat_count, len(node.repeats))

    return (total, max_repeat_count)


def compute_max_single_day(timerange: TimeRange) -> int:
    """Get the maximum number of tasks completed on a single day."""
    if not timerange.timeline:
        return 0
    return max(timerange.timeline.values())


def compute_avg_tasks_per_day(timerange: TimeRange, total_count: int) -> float:
    """Compute average tasks per day."""
    if timerange.earliest is None or timerange.latest is None:
        return 0.0

    days_spanned = (timerange.latest.date() - timerange.earliest.date()).days + 1
    if days_spanned <= 0:
        return 0.0

    return total_count / days_spanned


def compute_task_state_histogram(nodes: list[Heading]) -> Distribution:
    """Compute histogram of task states across all nodes."""
    task_states = Distribution(values={})

    for node in nodes:
        if node.repeats:
            for repeated_task in node.repeats:
                repeat_state = repeated_task.after or "null"
                task_states.update(repeat_state, 1)
        else:
            node_state = node.todo or "null"
            task_states.update(node_state, 1)

    return task_states


def compute_day_of_week_histogram(nodes: list[Heading]) -> Distribution:
    """Compute histogram of task completion days across all tasks."""
    task_days = Distribution(values={})

    for node in nodes:
        count = max(1, len(node.repeats))
        timestamps = extract_timestamp_any(node)

        if timestamps:
            for timestamp in timestamps:
                day_name = weekday_to_string(timestamp.weekday())
                task_days.update(day_name, 1)
        else:
            task_days.update("unknown", count)

    return task_days


def compute_category_histogram(nodes: list[Heading]) -> Distribution:
    """Compute histogram based on effective heading category values."""
    task_categories = Distribution(values={})

    for node in nodes:
        count = max(1, len(node.repeats))
        category_value = node.category
        if category_value is None or str(category_value) == "":
            category = "null"
        else:
            category = str(category_value)
        task_categories.update(category, count)

    return task_categories


def compute_priority_histogram(nodes: list[Heading]) -> Distribution:
    """Compute histogram of task priorities across all nodes."""
    task_priorities = Distribution(values={})

    for node in nodes:
        count = max(1, len(node.repeats))
        priority = node.priority
        priority_key = "null" if priority is None or str(priority) == "" else str(priority)
        task_priorities.update(priority_key, count)

    return task_priorities


def compute_global_timerange(nodes: list[Heading]) -> TimeRange:
    """Compute global time range across all tasks."""
    global_timerange = TimeRange()

    for node in nodes:
        timestamps = extract_timestamp_any(node)
        for timestamp in timestamps:
            global_timerange.update(timestamp)

    return global_timerange


def compute_frequencies(
    nodes: list[Heading],
    mapping: dict[str, str],
    category: str,
) -> dict[str, Frequency]:
    """Compute frequency statistics for all nodes in a given category."""
    frequencies: dict[str, Frequency] = {}

    for node in nodes:
        items = _extract_items(node, mapping, category)
        count = max(1, len(node.repeats))

        for item in items:
            if item not in frequencies:
                frequencies[item] = Frequency()
            frequencies[item].total += count

    return frequencies


def compute_relations(
    nodes: list[Heading],
    mapping: dict[str, str],
    category: str,
) -> dict[str, Relations]:
    """Compute pair-wise relations for all nodes in a given category."""
    relations_dict: dict[str, Relations] = {}

    for node in nodes:
        items = _extract_items(node, mapping, category)
        count = max(1, len(node.repeats))

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


def compute_time_ranges(
    nodes: list[Heading],
    mapping: dict[str, str],
    category: str,
) -> dict[str, TimeRange]:
    """Compute time ranges for all tasks in a given category."""
    time_ranges: dict[str, TimeRange] = {}

    for node in nodes:
        items = _extract_items(node, mapping, category)
        timestamps = extract_timestamp_any(node)

        if not timestamps:
            continue

        for item in items:
            if item not in time_ranges:
                time_ranges[item] = TimeRange()

            for timestamp in timestamps:
                time_ranges[item].update(timestamp)

    return time_ranges


def _combine_time_ranges(tag_time_ranges: dict[str, TimeRange], tags: list[str]) -> TimeRange:
    """Combine time ranges from multiple tags into a single TimeRange."""
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


def compute_per_tag_statistics(
    frequencies: dict[str, Frequency],
    relations: dict[str, Relations],
    time_ranges: dict[str, TimeRange],
) -> dict[str, Tag]:
    """Compute complete Tag objects with all statistics."""
    tags: dict[str, Tag] = {}

    for tag_name, frequency in frequencies.items():
        time_range = time_ranges.get(tag_name, TimeRange())
        relation = relations.get(tag_name, Relations(name=tag_name, relations={}))

        avg_per_day = compute_avg_tasks_per_day(time_range, frequency.total)
        max_single_day = compute_max_single_day(time_range)

        tags[tag_name] = Tag(
            name=tag_name,
            total_tasks=frequency.total,
            avg_tasks_per_day=avg_per_day,
            max_single_day_count=max_single_day,
            relations=relation.relations,
            time_range=time_range,
        )

    return tags


def compute_groups(  # noqa: C901
    tags: dict[str, Tag],
    max_relations: int,
    nodes: list[Heading],
    mapping: dict[str, str],
    category: str,
) -> list[Group]:
    """Compute strongly connected components from tag relations using Tarjan's algorithm."""
    if not tags:
        return []

    graph: dict[str, list[str]] = {}
    for tag_name, tag_obj in tags.items():
        sorted_relations = sorted(tag_obj.relations.items(), key=lambda x: -x[1])
        top_relations = sorted_relations[:max_relations]
        graph[tag_name] = [rel_name for rel_name, _ in top_relations]

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

    tag_time_ranges = {tag_name: tag_obj.time_range for tag_name, tag_obj in tags.items()}
    groups = []
    for scc in sccs:
        combined_time_range = _combine_time_ranges(tag_time_ranges, scc)

        groups.append(
            Group(
                tags=sorted(scc),
                time_range=combined_time_range,
                total_tasks=0,
                avg_tasks_per_day=0,
                max_single_day_count=0,
            ),
        )

    for org_node in nodes:
        node_items = _extract_items(org_node, mapping, category)

        for group in groups:
            scc_set = set(group.tags)

            if node_items & scc_set:
                group.total_tasks += max(1, len(org_node.repeats))

    for group in groups:
        group.avg_tasks_per_day = compute_avg_tasks_per_day(group.time_range, group.total_tasks)
        group.max_single_day_count = compute_max_single_day(group.time_range)

    return groups


def compute_explicit_groups(
    nodes: list[Heading],
    mapping: dict[str, str],
    category: str,
    group_items: list[list[str]],
    tag_time_ranges: dict[str, TimeRange],
) -> list[Group]:
    """Compute group statistics based on explicit tag lists."""
    groups: list[Group] = []

    for group in group_items:
        present_tags = [tag for tag in group if tag in tag_time_ranges]
        if not present_tags:
            continue

        group_set = set(present_tags)
        total_tasks = 0

        for node in nodes:
            node_items = _extract_items(node, mapping, category)
            if node_items & group_set:
                total_tasks += max(1, len(node.repeats))

        if total_tasks == 0:
            continue

        time_range = _combine_time_ranges(tag_time_ranges, present_tags)
        avg_tasks_per_day = compute_avg_tasks_per_day(time_range, total_tasks)
        max_single_day = compute_max_single_day(time_range)

        groups.append(
            Group(
                tags=present_tags,
                time_range=time_range,
                total_tasks=total_tasks,
                avg_tasks_per_day=avg_tasks_per_day,
                max_single_day_count=max_single_day,
            ),
        )

    return groups


def analyze(
    nodes: list[Heading],
    mapping: dict[str, str],
    category: str,
    max_relations: int,
) -> AnalysisResult:
    """Analyze org-mode nodes and extract task statistics."""
    tag_frequencies = compute_frequencies(nodes, mapping, category)
    tag_relations = compute_relations(nodes, mapping, category)
    tag_time_ranges = compute_time_ranges(nodes, mapping, category)
    tags = compute_per_tag_statistics(tag_frequencies, tag_relations, tag_time_ranges)
    tag_groups = compute_groups(tags, max_relations, nodes, mapping, category)
    task_states = compute_task_state_histogram(nodes)
    task_categories = compute_category_histogram(nodes)
    task_priorities = compute_priority_histogram(nodes)
    task_days = compute_day_of_week_histogram(nodes)
    global_timerange = compute_global_timerange(nodes)
    total, max_repeat_count = compute_task_stats(nodes)
    unique = len(nodes)
    max_single_day = compute_max_single_day(global_timerange)
    avg_tasks_per_day = compute_avg_tasks_per_day(global_timerange, total)

    return AnalysisResult(
        total_tasks=total,
        unique_tasks=unique,
        task_states=task_states,
        task_categories=task_categories,
        task_priorities=task_priorities,
        task_days=task_days,
        timerange=global_timerange,
        avg_tasks_per_day=avg_tasks_per_day,
        max_single_day_count=max_single_day,
        max_repeat_count=max_repeat_count,
        tags=tags,
        tag_groups=tag_groups,
    )


def clean(disallowed: set[str], tags: dict[str, Tag]) -> dict[str, Tag]:
    """Remove tags from the disallowed set (stop words)."""
    disallowed_lower = {d.lower() for d in disallowed}
    return {t: tags[t] for t in tags if t.lower() not in disallowed_lower}


def normalize_show_value(value: str, mapping: dict[str, str]) -> str:
    """Normalize a single show value to match heading/body analysis."""
    normalized = normalize({value}, mapping)
    return next(iter(normalized), "")


def dedupe_values(values: list[str]) -> list[str]:
    """Deduplicate values while preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def resolve_group_values(
    groups: list[str] | None,
    mapping: dict[str, str],
    category: str,
) -> list[list[str]] | None:
    """Resolve explicit group values from CLI arguments."""
    if groups is None:
        return None

    resolved_groups: list[list[str]] = []
    for group_value in groups:
        raw_values = parse_group_values(group_value)
        if category == "tags":
            group_items = [mapping.get(value, value) for value in raw_values]
        else:
            group_items = []
            for value in raw_values:
                normalized_value = normalize_show_value(value, mapping)
                if normalized_value:
                    group_items.append(normalized_value)
        group_items = dedupe_values(group_items)
        if group_items:
            resolved_groups.append(group_items)

    return resolved_groups
