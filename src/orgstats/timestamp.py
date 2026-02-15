"""Timestamp extraction and normalization functions."""

from datetime import date, datetime

import orgparse


def normalize_timestamp(ts: datetime | date) -> datetime:
    """Normalize all timestamps to use the datetime format

    Args:
        ts: datetime or date

    Returns:
        datetime
    """
    if not isinstance(ts, datetime):
        return datetime.combine(ts, datetime.min.time())
    return ts


def extract_timestamp(node: orgparse.node.OrgNode, done_keys: list[str]) -> list[datetime]:
    """Extract timestamps from a node following priority rules.

    Priority order:
    1. Repeated tasks (all completed tasks)
    2. Closed timestamp
    3. Scheduled timestamp
    4. Deadline timestamp
    5. Datelist (timestamps in body)

    Args:
        node: Org-mode node to extract timestamps from
        done_keys: List of completion state keywords

    Returns:
        List of datetime objects (may be empty if no timestamps found)
    """
    timestamps = []

    if node.repeated_tasks and any(rt.after in done_keys for rt in node.repeated_tasks):
        timestamps.extend([rt.start for rt in node.repeated_tasks if rt.after in done_keys])
    elif node.closed and node.closed.start:
        timestamps.append(node.closed.start)
    elif node.scheduled and node.scheduled.start:
        timestamps.append(node.scheduled.start)
    elif node.deadline and node.deadline.start:
        timestamps.append(node.deadline.start)
    elif node.datelist:
        timestamps.extend([d.start for d in node.datelist if d.start])

    return [normalize_timestamp(t) for t in timestamps]


def extract_timestamp_any(node: orgparse.node.OrgNode) -> list[datetime]:
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

    if node.repeated_tasks:
        timestamps.extend([rt.start for rt in node.repeated_tasks])
    elif node.closed and node.closed.start:
        timestamps.append(node.closed.start)
    elif node.scheduled and node.scheduled.start:
        timestamps.append(node.scheduled.start)
    elif node.deadline and node.deadline.start:
        timestamps.append(node.deadline.start)
    elif node.datelist:
        timestamps.extend([d.start for d in node.datelist if d.start])

    return [normalize_timestamp(t) for t in timestamps]
