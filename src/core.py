"""Core logic for orgstats - Org-mode archive file analysis."""

from typing import Any


MAP = {
    'test': "testing",
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
    "dia": "softwarearchitecture"
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
    else:
        return t


def normalize(tags: set[str]) -> set[str]:
    """Normalize tags by lowercasing, stripping whitespace, removing punctuation,
    and mapping to canonical forms.
    
    Args:
        tags: Set of tags to normalize
        
    Returns:
        Set of normalized and mapped tags
    """
    norm = { t.lower()
             .strip()
             .replace(".", "")
             .replace(":", "")
             .replace("!", "")
             .replace(",", "")
             .replace(";", "")
             .replace("?", "") for t in tags }
    return { mapped(MAP, t) for t in norm }


def analyze(nodes: list[Any]) -> tuple[int, int, dict[str, int], dict[str, int], dict[str, int]]:
    """Analyze org-mode nodes and extract task statistics.
    
    Args:
        nodes: List of org-mode nodes from orgparse
        
    Returns:
        Tuple of (total_tasks, done_tasks, tag_frequencies, heading_word_frequencies, body_word_frequencies)
    """
    total = 0
    done = 0
    tags = dict()
    heading = dict()
    words = dict()

    for node in nodes:
        total = total + max(1, len(node.repeated_tasks))

        final = node.todo == "DONE" and 1 or 0
        repeats = len([n for n in node.repeated_tasks if n.after == "DONE"])
        count = max(final, repeats)

        done = done + count

        for tag in normalize(node.tags):
            if tag in tags:
                tags[tag] = tags[tag] + count
            else:
                tags[tag] = count

        for tag in normalize(set(node.heading.split())):
            if tag in heading:
                heading[tag] = heading[tag] + count
            else:
                heading[tag] = count

        for tag in normalize(set(node.body.split())):
            if tag in words:
                words[tag] = words[tag] + count
            else:
                words[tag] = count

    return (total, done, tags, heading, words)


TAGS = {
    "comp", "computer", "uni", "homework", "test", "blog", "lecture", "due",
    "cleaning", "germanvocabulary", "readingkorean", "readingenglish", "englishvocabulary",
    "lifehacking", "tinkering"
}


HEADING = {
    "the", "to", "a", "for", "in", "of", "and", "on", "with", "some", "out", "&", "up", "from", "an", "into", "new", "why",
    "suspended", "hangul", "romanization", "do", "dishes", "medial", "clean", "tidy", "sweep", "living", "room", "bathroom",
    "kitchen", "ways", "say", "bill", "piwl", "piwm"
}


WORDS = HEADING.union({
    "end", "logbook", "cancelled", "scheduled", "suspended", "it", "this", "do", "is", "no", "not", "that", "all",
    "but", "be", "use", "now", "will", "an", "i", "as", "or", "by", "did", "can", "->", "are", "was", "[x]", "meh", "more",
    "until", "+", "using", "when", "into", "only", "at", "it's", "have", "about", "just", "2", "etc", "get", "didn't",
    "can't", "lu", "lu's", "lucyna", "alicja", "my", "does", "nah", "there", "yet", "nope", "should", "i'll",
    "khhhhaaaaannn't", "zrobiła", "robi", "dysze",
    "pon", "wto", "śro", "czw", "pią", "sob", "nie",
    "", "'localhost6667/lucynajaworska'", "'localhost6667/&bitlbee'", "file~/org/refileorg", "[2012-11-27", "++1d]",
    "#+begin_src", "#+end_src", "-", "=", "|", "(", ")", "[2022-07-05"
})


def clean(allowed: set[str], tags: dict[str, int]) -> dict[str, int]:
    """Remove tags from the allowed set (stop words).
    
    Args:
        allowed: Set of tags to filter out (stop words)
        tags: Dictionary of tag frequencies
        
    Returns:
        Dictionary with allowed tags removed
    """
    return {t: tags[t] for t in tags if t not in allowed}
