"""Core logic for orgstats - Org-mode archive file analysis."""

from dataclasses import dataclass

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
class AnalysisResult:
    """Represents the complete result of analyzing Org-mode nodes.

    Attributes:
        total_tasks: Total number of tasks analyzed
        done_tasks: Number of completed tasks
        tag_frequencies: Dictionary mapping tags to their frequency counts
        heading_frequencies: Dictionary mapping heading words to their frequency counts
        body_frequencies: Dictionary mapping body words to their frequency counts
    """

    total_tasks: int
    done_tasks: int
    tag_frequencies: dict[str, Frequency]
    heading_frequencies: dict[str, Frequency]
    body_frequencies: dict[str, Frequency]


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

    for node in nodes:
        total = total + max(1, len(node.repeated_tasks))

        final = (node.todo == "DONE" and 1) or 0
        repeats = len([n for n in node.repeated_tasks if n.after == "DONE"])
        count = max(final, repeats)

        done = done + count

        for tag in normalize(node.tags):
            if tag not in tags:
                tags[tag] = Frequency()
            tags[tag].total += count

        for tag in normalize(set(node.heading.split())):
            if tag not in heading:
                heading[tag] = Frequency()
            heading[tag].total += count

        for tag in normalize(set(node.body.split())):
            if tag not in words:
                words[tag] = Frequency()
            words[tag].total += count

    return AnalysisResult(
        total_tasks=total,
        done_tasks=done,
        tag_frequencies=tags,
        heading_frequencies=heading,
        body_frequencies=words,
    )


TAGS = {
    "comp",
    "computer",
    "uni",
    "homework",
    "test",
    "blog",
    "lecture",
    "due",
    "cleaning",
    "germanvocabulary",
    "readingkorean",
    "readingenglish",
    "englishvocabulary",
    "lifehacking",
    "tinkering",
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
