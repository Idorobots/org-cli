"""Shared test fixtures and utilities for orgstats tests."""

from typing import Any

import orgparse

from orgstats.core import Frequency


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


def node_from_org(org_text: str) -> list[Any]:
    """Parse org-mode text and return list of nodes (excluding root).

    Args:
        org_text: Org-mode formatted text

    Returns:
        List of OrgNode objects (excluding root node)
    """
    root = orgparse.loads(org_text.replace("24:00", "00:00"))
    return list(root[1:]) if root else []
