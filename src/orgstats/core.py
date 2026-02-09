"""Core logic for orgstats - Org-mode archive file analysis."""

from dataclasses import dataclass, field
from datetime import date, datetime

import orgparse


@dataclass
class Frequency:  # noqa: PLW1641
    """Represents frequency statistics for a tag/word.

    Attributes:
        total: Total count for this item
    """

    total: int = 0

    def __repr__(self) -> str:
        """Return string representation of Frequency."""
        return f"Frequency(total={self.total})"

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
class Relations:
    """Represents pair-wise co-occurrence relationships for a tag/word.

    Attributes:
        name: The tag or word name
        relations: Dictionary mapping related tags/words to co-occurrence counts
    """

    name: str
    relations: dict[str, int]

    def __repr__(self) -> str:
        """Return string representation of Relations."""
        return f"Relations(name={self.name!r}, relations={self.relations})"


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
class AnalysisResult:
    """Represents the complete result of analyzing Org-mode nodes.

    Attributes:
        total_tasks: Total number of tasks analyzed
        done_tasks: Number of completed tasks
        tag_frequencies: Dictionary mapping items to their frequency counts
        tag_relations: Dictionary mapping items to their Relations objects
        tag_time_ranges: Dictionary mapping items to their TimeRange objects

    Note: Despite the 'tag_' prefix, these fields hold data for whichever
    category was analyzed (tags, heading, or body).
    """

    total_tasks: int
    done_tasks: int
    tag_frequencies: dict[str, Frequency]
    tag_relations: dict[str, Relations]
    tag_time_ranges: dict[str, TimeRange]


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


def compute_relations(items: set[str], relations_dict: dict[str, Relations], count: int) -> None:
    """Compute pair-wise relations for a set of items.

    Args:
        items: Set of items (tags or words) to compute relations for
        relations_dict: Dictionary to store Relations objects
        count: Count to increment relations by (for repeated tasks)
    """
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


def compute_frequencies(items: set[str], frequencies: dict[str, Frequency], count: int) -> None:
    """Compute frequency statistics for a set of items.

    Args:
        items: Set of items (tags or words) to compute frequencies for
        frequencies: Dictionary to store/update Frequency objects
        count: Count to increment frequencies by (for repeated tasks)
    """
    for item in items:
        if item not in frequencies:
            frequencies[item] = Frequency()
        frequencies[item].total += count


def extract_timestamp(node: orgparse.node.OrgNode) -> list[datetime]:
    """Extract timestamps from a node following priority rules.

    Priority order:
    1. Repeated tasks (all DONE tasks)
    2. Closed timestamp
    3. Scheduled timestamp
    4. Deadline timestamp

    Args:
        node: Org-mode node to extract timestamps from

    Returns:
        List of datetime objects (may be empty if no timestamps found)
    """
    timestamps = []

    if node.repeated_tasks:
        done_tasks = [rt for rt in node.repeated_tasks if rt.after == "DONE"]
        if done_tasks:
            timestamps.extend([rt.start for rt in done_tasks])
            return timestamps

    if hasattr(node, "closed") and node.closed and node.closed.start:
        timestamps.append(node.closed.start)
        return timestamps

    if hasattr(node, "scheduled") and node.scheduled and node.scheduled.start:
        timestamps.append(node.scheduled.start)
        return timestamps

    if hasattr(node, "deadline") and node.deadline and node.deadline.start:
        timestamps.append(node.deadline.start)
        return timestamps

    return timestamps


def compute_time_ranges(
    items: set[str], time_ranges: dict[str, TimeRange], timestamps: list[datetime]
) -> None:
    """Compute time ranges for a set of items.

    Args:
        items: Set of items (tags or words) to compute time ranges for
        time_ranges: Dictionary to store/update TimeRange objects
        timestamps: List of timestamps to incorporate
    """
    if not timestamps:
        return

    for item in items:
        if item not in time_ranges:
            time_ranges[item] = TimeRange()

        for timestamp in timestamps:
            time_ranges[item].update(timestamp)


def analyze(
    nodes: list[orgparse.node.OrgNode], mapping: dict[str, str], category: str
) -> AnalysisResult:
    """Analyze org-mode nodes and extract task statistics.

    Args:
        nodes: List of org-mode nodes from orgparse
        mapping: Dictionary mapping tags to canonical forms
        category: Which datum to analyze - "tags", "heading", or "body" (default: "tags")

    Returns:
        AnalysisResult containing task counts and frequency dictionaries for the selected category
    """
    total = 0
    done = 0
    frequencies: dict[str, Frequency] = {}
    relations: dict[str, Relations] = {}
    time_ranges: dict[str, TimeRange] = {}

    for node in nodes:
        total = total + max(1, len(node.repeated_tasks))

        final = (node.todo == "DONE" and 1) or 0
        repeats = len([n for n in node.repeated_tasks if n.after == "DONE"])
        count = max(final, repeats)

        done = done + count

        if category == "tags":
            items = normalize(node.tags, mapping)
        elif category == "heading":
            items = normalize(set(node.heading.split()), mapping)
        else:
            items = normalize(set(node.body.split()), mapping)

        compute_frequencies(items, frequencies, count)
        compute_relations(items, relations, count)

        timestamps = extract_timestamp(node)
        compute_time_ranges(items, time_ranges, timestamps)

    return AnalysisResult(
        total_tasks=total,
        done_tasks=done,
        tag_frequencies=frequencies,
        tag_relations=relations,
        tag_time_ranges=time_ranges,
    )


def clean(disallowed: set[str], tags: dict[str, Frequency]) -> dict[str, Frequency]:
    """Remove tags from the disallowed set (stop words).

    Args:
        disallowed: Set of tags to filter out (stop words)
        tags: Dictionary of tag frequencies

    Returns:
        Dictionary with disallowed tags removed
    """
    return {t: tags[t] for t in tags if t not in disallowed}
