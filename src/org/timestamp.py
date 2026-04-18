"""Timestamp extraction and normalization functions."""

from datetime import date, datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from org_parser.document import Heading


def normalize_timestamp(ts: datetime | date) -> datetime:
    """Normalize all timestamps to use the datetime format.

    Args:
        ts: datetime or date

    Returns:
        datetime
    """
    if not isinstance(ts, datetime):
        return datetime.combine(ts, datetime.min.time())
    return ts


def extract_timestamp(node: Heading, done_states: list[str]) -> list[datetime]:
    """Extract timestamps from a node following priority rules.

    Priority order:
    1. Repeated tasks (all completed tasks)
    2. Closed timestamp
    3. Scheduled timestamp
    4. Deadline timestamp
    5. Datelist (timestamps in body)

    Args:
        node: Org-mode node to extract timestamps from
        done_states: List of completion state keywords

    Returns:
        List of datetime objects (may be empty if no timestamps found)
    """
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
    """Extract timestamps from a node without filtering by completion state.

    Priority order:
    1. Repeated tasks (all repeated tasks regardless of state)
    2. Closed timestamp
    3. Scheduled timestamp
    4. Deadline timestamp
    5. Datelist (timestamps in body)

    Args:
        node: Org-mode node to extract timestamps from

    Returns:
        List of datetime objects (may be empty if no timestamps found)
    """
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
