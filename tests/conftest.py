"""Shared test fixtures and utilities for org tests."""

from typing import TYPE_CHECKING

import org_parser


if TYPE_CHECKING:
    from org_parser.document import Heading


def node_from_org(
    org_text: str,
    todo_states: list[str] | None = None,
    done_states: list[str] | None = None,
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
