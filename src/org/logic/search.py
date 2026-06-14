"""Shared search helpers for interactive command filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from org_parser.document import Heading


def node_search_text(node: Heading) -> str:
    """Build searchable text from one node without including child subtrees."""
    parts: list[str] = [
        str(node.title_text),
        str(node.body_text),
        str(node.todo or ""),
        str(node.priority or ""),
        str(node.id or ""),
    ]

    parts.extend(str(tag) for tag in node.tags)
    parts.extend(str(tag) for tag in node.heading_tags)

    for key, value in node.properties.items():
        parts.append(str(key))
        parts.append(str(value))

    parts.extend(
        str(timestamp)
        for timestamp in (node.scheduled, node.deadline, node.closed)
        if timestamp is not None
    )

    parts.extend(str(repeat) for repeat in node.repeats)
    return "\n".join(parts)


def filter_nodes_by_search(nodes: list[Heading], search_text: str) -> list[Heading]:
    """Filter nodes by case-insensitive substring match over one node's own text."""
    normalized_search = search_text.strip().casefold()
    if not normalized_search:
        return list(nodes)

    return [node for node in nodes if normalized_search in node_search_text(node).casefold()]
