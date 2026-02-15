"""Shared test fixtures and utilities for orgstats tests."""

import orgparse

from orgstats.analyze import Frequency


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
    org_text: str, todo_keys: list[str] | None = None, done_keys: list[str] | None = None
) -> list[orgparse.node.OrgNode]:
    """Parse org-mode text and return list of nodes (excluding root).

    Args:
        org_text: Org-mode formatted text
        todo_keys: List of TODO state keywords (default: ["TODO"])
        done_keys: List of DONE state keywords (default: ["DONE"])

    Returns:
        List of OrgNode objects (excluding root node)
    """
    if todo_keys is None:
        todo_keys = ["TODO"]
    if done_keys is None:
        done_keys = ["DONE"]

    todo_config = f"#+TODO: {' '.join(todo_keys)} | {' '.join(done_keys)}\n\n"
    content = org_text.replace("24:00", "00:00")
    content = todo_config + content

    root = orgparse.loads(content)
    return list(root[1:]) if root else []
