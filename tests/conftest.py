"""Shared test fixtures and utilities for org tests."""

import org_parser
from org_parser.document import Heading

from org.analyze import Frequency


def freq_dict_from_ints(d: dict[str, int]) -> dict[str, Frequency]:
    """Convert dict[str, int] to dict[str, Frequency] for testing.

    Args:
        d: Dictionary mapping strings to integers

    Returns:
        Dictionary mapping strings to Frequency objects
    """
    return {k: Frequency(v) for k, v in d.items()}


def freq_dict_to_ints(d: dict[str, Frequency]) -> dict[str, int]:
    """Convert dict[str, Frequency] to dict[str, int] for assertions.

    Args:
        d: Dictionary mapping strings to Frequency objects

    Returns:
        Dictionary mapping strings to integers
    """
    return {k: v.total for k, v in d.items()}


def node_from_org(
    org_text: str, todo_states: list[str] | None = None, done_states: list[str] | None = None
) -> list[Heading]:
    """Parse org-mode text and return list of nodes (excluding root).

    Args:
        org_text: Org-mode formatted text
        todo_states: List of TODO state keywords (default: ["TODO"])
        done_states: List of DONE state keywords (default: ["DONE"])

    Returns:
        List of Heading objects (excluding root node)
    """
    if todo_states is None:
        todo_states = ["TODO"]
    if done_states is None:
        done_states = ["DONE"]

    todo_config = f"#+TODO: {' '.join(todo_states)} | {' '.join(done_states)}\n\n"
    content = org_text.replace("24:00", "00:00")
    content = todo_config + content

    root = org_parser.loads(content)
    return list(root)
