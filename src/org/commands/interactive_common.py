"""Shared helpers retained across interactive command implementations."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from org_parser.element import Repeat
from org_parser.time import Timestamp


if TYPE_CHECKING:
    from org_parser.document import Heading


@dataclass(frozen=True)
class HeadingLocator:
    """Stable heading locator used to restore selection across reloads."""

    filename: str
    heading_id: str | None
    title: str


def local_now() -> datetime:
    """Return local timezone-aware current datetime."""
    return datetime.now(tz=UTC).astimezone()


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


def set_timestamp_fields(timestamp: Timestamp, start: datetime, end: datetime | None) -> None:
    """Set timestamp date/time fields while preserving active/repeater metadata."""
    timestamp.start_year = start.year
    timestamp.start_month = start.month
    timestamp.start_day = start.day
    timestamp.start_dayname = start.strftime("%a")
    if timestamp.start_hour is not None:
        timestamp.start_hour = start.hour
        timestamp.start_minute = start.minute

    if end is None or timestamp.end is None:
        return

    timestamp.end_year = end.year
    timestamp.end_month = end.month
    timestamp.end_day = end.day
    timestamp.end_dayname = end.strftime("%a")
    if timestamp.end_hour is not None:
        timestamp.end_hour = end.hour
        timestamp.end_minute = end.minute


def add_months(value: datetime, months: int) -> datetime:
    """Add months to a datetime while clamping day to month length."""
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def shift_datetimes_by_unit(
    start: datetime,
    end: datetime | None,
    *,
    value: int,
    unit: str,
) -> tuple[datetime, datetime | None]:
    """Shift start/end datetimes by one repeater unit."""
    if unit == "d":
        delta = timedelta(days=value)
        return start + delta, None if end is None else end + delta
    if unit == "w":
        delta = timedelta(weeks=value)
        return start + delta, None if end is None else end + delta
    if unit == "h":
        delta = timedelta(hours=value)
        return start + delta, None if end is None else end + delta
    if unit == "m":
        return add_months(start, value), None if end is None else add_months(end, value)
    if unit == "y":
        months = value * 12
        return add_months(start, months), None if end is None else add_months(end, months)
    raise ValueError(f"Unsupported repeater unit: {unit}")


def now_aligned_for_datetime(start: datetime, now: datetime) -> datetime:
    """Normalize current datetime to match timezone-awareness of start."""
    if start.tzinfo is None:
        return now.replace(tzinfo=None)
    if now.tzinfo is None:
        return now.replace(tzinfo=start.tzinfo)
    return now.astimezone(start.tzinfo)


def advance_timestamp_by_repeater(timestamp: Timestamp) -> bool:
    """Advance timestamp once by its repeater marker, when present."""
    if timestamp.repeater is None:
        return False

    mark = timestamp.repeater.mark
    value = timestamp.repeater.value
    unit = timestamp.repeater.unit
    if value <= 0:
        return False

    start = timestamp.start
    end = timestamp.end

    try:
        if mark == "+":
            shifted_start, shifted_end = shift_datetimes_by_unit(
                start,
                end,
                value=value,
                unit=unit,
            )
        elif mark == "++":
            now = now_aligned_for_datetime(start, local_now())
            shifted_start, shifted_end = shift_datetimes_by_unit(
                start,
                end,
                value=value,
                unit=unit,
            )
            while shifted_start <= now:
                shifted_start, shifted_end = shift_datetimes_by_unit(
                    shifted_start,
                    shifted_end,
                    value=value,
                    unit=unit,
                )
        elif mark == ".+":
            now = now_aligned_for_datetime(start, local_now())
            base_start = start.replace(year=now.year, month=now.month, day=now.day)
            base_end = None if end is None else base_start + (end - start)
            shifted_start, shifted_end = shift_datetimes_by_unit(
                base_start,
                base_end,
                value=value,
                unit=unit,
            )
        else:
            return False
    except ValueError:
        return False

    set_timestamp_fields(timestamp, shifted_start, shifted_end)
    return True


def detail_org_block(node: Heading) -> str:
    """Return one heading subtree rendered back to Org text."""
    parts = [str(node)]
    parts.extend(detail_org_block(child) for child in node.children)
    return "".join(parts)
