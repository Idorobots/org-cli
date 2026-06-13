"""Shared task manipulation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from org_parser.element import Repeat
from org_parser.time import Timestamp


if TYPE_CHECKING:
    from datetime import datetime

    from org_parser.document import Heading


@dataclass(frozen=True)
class HeadingLocator:
    """Stable heading locator used to restore selection across reloads."""

    filename: str
    heading_id: str | None
    title: str


def shift_priority(priority: str | None, *, increase: bool) -> str | None:
    """Shift priority one step across A/B/C/none."""
    order: list[str | None] = ["A", "B", "C", None]
    normalized = priority if priority in {"A", "B", "C"} else None
    index = order.index(normalized)
    if increase:
        return order[max(0, index - 1)]
    return order[min(len(order) - 1, index + 1)]


def heading_locator(node: Heading) -> HeadingLocator:
    """Build a stable heading locator for selection restoration."""
    return HeadingLocator(
        filename=node.document.filename or "",
        heading_id=node.id,
        title=node.title_text,
    )


def resolve_heading_locator(
    candidates: list[Heading],
    locator: HeadingLocator | None,
) -> Heading | None:
    """Resolve a preserved heading locator against a candidate heading list."""
    if locator is None or not candidates:
        return None

    document = None
    for candidate in candidates:
        if (candidate.document.filename or "") == locator.filename:
            document = candidate.document
            break
    if document is None:
        return None

    resolved = (
        document.heading_by_id(locator.heading_id)
        if locator.heading_id is not None
        else document.heading_by_title(locator.title)
    )
    if resolved is None:
        return None

    for candidate in candidates:
        if candidate is resolved:
            return candidate
    return None


def append_repeat_transition(
    heading: Heading,
    before: str | None,
    after: str | None,
    now: datetime,
) -> None:
    """Append one repeat transition entry at current time."""
    transition_time = now.replace(second=0, microsecond=0)
    heading.repeats.append(
        Repeat(
            before=before,
            after=after,
            timestamp=Timestamp.from_datetime(transition_time, is_active=False),
        ),
    )


def detail_org_block(node: Heading) -> str:
    """Return one heading subtree rendered back to Org text."""
    parts = [str(node)]
    parts.extend(detail_org_block(child) for child in node.children)
    return "".join(parts)
