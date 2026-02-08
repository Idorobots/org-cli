"""Core logic for orgstats - Org-mode archive file analysis."""

from dataclasses import dataclass
from datetime import date, datetime

import orgparse


@dataclass
class Frequency:  # noqa: PLW1641
    """Represents frequency statistics for a tag/word.

    Attributes:
        total: Total count for this item
        simple: Count of simple tasks (gamify_exp < 10)
        regular: Count of regular tasks (10 <= gamify_exp < 20)
        hard: Count of hard tasks (gamify_exp >= 20)
    """

    total: int = 0
    simple: int = 0
    regular: int = 0
    hard: int = 0

    def __repr__(self) -> str:
        """Return string representation of Frequency."""
        return (
            f"Frequency(total={self.total}, simple={self.simple}, "
            f"regular={self.regular}, hard={self.hard})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare with another Frequency or int.

        Args:
            other: Object to compare with (Frequency or int)

        Returns:
            True if equal, False otherwise
        """
        if isinstance(other, Frequency):
            return (
                self.total == other.total
                and self.simple == other.simple
                and self.regular == other.regular
                and self.hard == other.hard
            )
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
    """

    earliest: datetime | None = None
    latest: datetime | None = None

    def __repr__(self) -> str:
        """Return string representation of TimeRange."""
        return f"TimeRange(earliest={self.earliest}, latest={self.latest})"

    def update(self, timestamp: datetime | date) -> None:
        """Update time range with a new timestamp.

        Args:
            timestamp: Timestamp to incorporate into the range (datetime or date)
        """
        if isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            timestamp = datetime.combine(timestamp, datetime.min.time())

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
        tag_frequencies: Dictionary mapping tags to their frequency counts
        heading_frequencies: Dictionary mapping heading words to their frequency counts
        body_frequencies: Dictionary mapping body words to their frequency counts
        tag_relations: Dictionary mapping tags to their Relations objects
        heading_relations: Dictionary mapping heading words to their Relations objects
        body_relations: Dictionary mapping body words to their Relations objects
        tag_time_ranges: Dictionary mapping tags to their TimeRange objects
        heading_time_ranges: Dictionary mapping heading words to their TimeRange objects
        body_time_ranges: Dictionary mapping body words to their TimeRange objects
    """

    total_tasks: int
    done_tasks: int
    tag_frequencies: dict[str, Frequency]
    heading_frequencies: dict[str, Frequency]
    body_frequencies: dict[str, Frequency]
    tag_relations: dict[str, Relations]
    heading_relations: dict[str, Relations]
    body_relations: dict[str, Relations]
    tag_time_ranges: dict[str, TimeRange]
    heading_time_ranges: dict[str, TimeRange]
    body_time_ranges: dict[str, TimeRange]


MAP = {
    "test": "testing",
    "sysadmin": "devops",
    "pldesign": "compilers",
    "webdev": "frontend",
    "unix": "linux",
    "gtd": "agile",
    "foof": "spartan",
    "typing": "documenting",
    "notestaking": "documenting",
    "computernetworks": "networking",
    "maintenance": "refactoring",
    "softwareengineering": "softwarearchitecture",
    "soa": "softwarearchitecture",
    "uml": "softwarearchitecture",
    "dia": "softwarearchitecture",
}


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


def normalize(tags: set[str]) -> set[str]:
    """Normalize tags by lowercasing, stripping whitespace, removing punctuation,
    and mapping to canonical forms.

    Args:
        tags: Set of tags to normalize

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
    return {mapped(MAP, t) for t in norm}


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


def compute_frequencies(
    items: set[str], frequencies: dict[str, Frequency], count: int, difficulty: str
) -> None:
    """Compute frequency statistics for a set of items.

    Args:
        items: Set of items (tags or words) to compute frequencies for
        frequencies: Dictionary to store/update Frequency objects
        count: Count to increment frequencies by (for repeated tasks)
        difficulty: Task difficulty level ("simple", "regular", or "hard")
    """
    for item in items:
        if item not in frequencies:
            frequencies[item] = Frequency()
        frequencies[item].total += count
        if difficulty == "simple":
            frequencies[item].simple += count
        elif difficulty == "regular":
            frequencies[item].regular += count
        else:
            frequencies[item].hard += count


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


def analyze(nodes: list[orgparse.node.OrgNode]) -> AnalysisResult:
    """Analyze org-mode nodes and extract task statistics.

    Args:
        nodes: List of org-mode nodes from orgparse

    Returns:
        AnalysisResult containing task counts and frequency dictionaries
    """
    total = 0
    done = 0
    tags: dict[str, Frequency] = {}
    heading: dict[str, Frequency] = {}
    words: dict[str, Frequency] = {}
    tag_relations: dict[str, Relations] = {}
    heading_relations: dict[str, Relations] = {}
    body_relations: dict[str, Relations] = {}
    tag_time_ranges: dict[str, TimeRange] = {}
    heading_time_ranges: dict[str, TimeRange] = {}
    body_time_ranges: dict[str, TimeRange] = {}

    for node in nodes:
        total = total + max(1, len(node.repeated_tasks))

        final = (node.todo == "DONE" and 1) or 0
        repeats = len([n for n in node.repeated_tasks if n.after == "DONE"])
        count = max(final, repeats)

        done = done + count

        gamify_exp_raw = node.properties.get("gamify_exp", None)
        gamify_exp_str = str(gamify_exp_raw) if gamify_exp_raw is not None else None
        gamify_exp = parse_gamify_exp(gamify_exp_str)

        if gamify_exp is None:
            difficulty = "regular"
        elif gamify_exp < 10:
            difficulty = "simple"
        elif gamify_exp < 20:
            difficulty = "regular"
        else:
            difficulty = "hard"

        normalized_tags = normalize(node.tags)
        normalized_heading = normalize(set(node.heading.split()))
        normalized_body = normalize(set(node.body.split()))

        compute_frequencies(normalized_tags, tags, count, difficulty)
        compute_frequencies(normalized_heading, heading, count, difficulty)
        compute_frequencies(normalized_body, words, count, difficulty)

        compute_relations(normalized_tags, tag_relations, count)
        compute_relations(normalized_heading, heading_relations, count)
        compute_relations(normalized_body, body_relations, count)

        timestamps = extract_timestamp(node)
        compute_time_ranges(normalized_tags, tag_time_ranges, timestamps)
        compute_time_ranges(normalized_heading, heading_time_ranges, timestamps)
        compute_time_ranges(normalized_body, body_time_ranges, timestamps)

    return AnalysisResult(
        total_tasks=total,
        done_tasks=done,
        tag_frequencies=tags,
        heading_frequencies=heading,
        body_frequencies=words,
        tag_relations=tag_relations,
        heading_relations=heading_relations,
        body_relations=body_relations,
        tag_time_ranges=tag_time_ranges,
        heading_time_ranges=heading_time_ranges,
        body_time_ranges=body_time_ranges,
    )


TAGS = {
    "comp",
    "computer",
    "uni",
    "out",
    "home",
    "exam",
    "note",
    "learn",
    "homework",
    "test",
    "blog",
    "plan",
    "lecture",
    "due",
    "cleaning",
    "germanvocabulary",
    "readingkorean",
    "readingenglish",
    "englishvocabulary",
    "lifehacking",
    "tinkering",
    "speakingenglish",
}


HEADING = {
    "the",
    "to",
    "a",
    "for",
    "in",
    "of",
    "and",
    "on",
    "with",
    "some",
    "out",
    "&",
    "up",
    "from",
    "an",
    "into",
    "new",
    "why",
    "suspended",
    "hangul",
    "romanization",
    "do",
    "dishes",
    "medial",
    "clean",
    "tidy",
    "sweep",
    "living",
    "room",
    "bathroom",
    "kitchen",
    "ways",
    "say",
    "bill",
    "piwl",
    "piwm",
}


BODY = HEADING.union(
    {
        "end",
        "logbook",
        "cancelled",
        "scheduled",
        "suspended",
        "it",
        "this",
        "do",
        "is",
        "no",
        "not",
        "that",
        "all",
        "but",
        "be",
        "use",
        "now",
        "will",
        "an",
        "i",
        "as",
        "or",
        "by",
        "did",
        "can",
        "->",
        "are",
        "was",
        "[x]",
        "meh",
        "more",
        "until",
        "+",
        "using",
        "when",
        "into",
        "only",
        "at",
        "it's",
        "have",
        "about",
        "just",
        "2",
        "etc",
        "get",
        "didn't",
        "can't",
        "lu",
        "lu's",
        "lucyna",
        "alicja",
        "my",
        "does",
        "nah",
        "there",
        "yet",
        "nope",
        "should",
        "i'll",
        "khhhhaaaaannn't",
        "zrobiła",
        "robi",
        "dysze",
        "pon",
        "wto",
        "śro",
        "czw",
        "pią",
        "sob",
        "nie",
        "",
        "'localhost6667/lucynajaworska'",
        "'localhost6667/&bitlbee'",
        "file~/org/refileorg",
        "[2012-11-27",
        "++1d]",
        "#+begin_src",
        "#+end_src",
        "-",
        "=",
        "|",
        "(",
        ")",
        "[2022-07-05",
        "+1w]",
        "(define",
        "//",
        "i'm",
        "0)",
        "[2019-02-09",
    }
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
