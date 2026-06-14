"""Timestamp and time-related logic."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import typer


if TYPE_CHECKING:
    from org_parser.document import Heading
    from org_parser.time import Timestamp


def local_now() -> datetime:
    """Return local timezone-aware current datetime."""
    return datetime.now(tz=UTC).astimezone()


def parse_date_argument(date_str: str, arg_name: str) -> datetime:
    """Parse and validate timestamp argument in multiple supported formats."""
    if not date_str or not date_str.strip():
        supported_formats = [
            "YYYY-MM-DD",
            "YYYY-MM-DDThh:mm",
            "YYYY-MM-DDThh:mm:ss",
            "YYYY-MM-DD hh:mm",
            "YYYY-MM-DD hh:mm:ss",
        ]
        formats_str = ", ".join(supported_formats)
        raise typer.BadParameter(
            f"{arg_name} must be in one of these formats: {formats_str}\nGot: '{date_str}'",
        )

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(date_str.replace(" ", "T"))
    except ValueError:
        pass

    supported_formats = [
        "YYYY-MM-DD",
        "YYYY-MM-DDThh:mm",
        "YYYY-MM-DDThh:mm:ss",
        "YYYY-MM-DD hh:mm",
        "YYYY-MM-DD hh:mm:ss",
    ]
    formats_str = ", ".join(supported_formats)
    raise typer.BadParameter(
        f"{arg_name} must be in one of these formats: {formats_str}\nGot: '{date_str}'",
    )


def normalize_timestamp(ts: datetime | date) -> datetime:
    """Normalize all timestamps to use the datetime format."""
    if not isinstance(ts, datetime):
        return datetime.combine(ts, datetime.min.time())
    return ts


def extract_timestamp(node: Heading, done_states: list[str]) -> list[datetime]:
    """Extract timestamps from a node following priority rules."""
    timestamps = []

    if node.repeats and any(rt.after in done_states for rt in node.repeats):
        timestamps.extend([rt.timestamp.start for rt in node.repeats if rt.after in done_states])
    elif node.closed:
        timestamps.append(node.closed.start)
    elif node.scheduled:
        timestamps.append(node.scheduled.start)
    elif node.deadline:
        timestamps.append(node.deadline.start)
    elif node.timestamps:
        timestamps.extend([timestamp.start for timestamp in node.timestamps])

    return [normalize_timestamp(t) for t in timestamps]


def extract_timestamp_any(node: Heading) -> list[datetime]:
    """Extract timestamps from a node without filtering by completion state."""
    timestamps = []

    if node.repeats:
        timestamps.extend([rt.timestamp.start for rt in node.repeats])
    elif node.closed:
        timestamps.append(node.closed.start)
    elif node.scheduled:
        timestamps.append(node.scheduled.start)
    elif node.deadline:
        timestamps.append(node.deadline.start)
    elif node.timestamps:
        timestamps.extend([timestamp.start for timestamp in node.timestamps])

    return [normalize_timestamp(t) for t in timestamps]


def resolve_date_filters(args: object) -> tuple[datetime | None, datetime | None]:
    """Resolve date filter arguments into parsed datetime values."""
    date_from_value = getattr(args, "filter_date_from", None)
    date_until_value = getattr(args, "filter_date_until", None)
    date_from = (
        parse_date_argument(date_from_value, "--filter-date-from")
        if date_from_value is not None
        else None
    )
    date_until = (
        parse_date_argument(date_until_value, "--filter-date-until")
        if date_until_value is not None
        else None
    )
    return date_from, date_until


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
