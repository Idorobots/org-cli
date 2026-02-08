"""Tests for the extract_timestamp() function."""

from datetime import datetime

from orgstats.core import extract_timestamp


class MockTimestamp:
    """Mock timestamp object."""

    def __init__(self, start):
        self.start = start


class MockRepeatedTask:
    """Mock repeated task."""

    def __init__(self, after, start):
        self.after = after
        self.start = start


class MockNode:
    """Mock node object for testing extract_timestamp()."""

    def __init__(self, repeated_tasks=None, closed=None, scheduled=None, deadline=None):
        self.repeated_tasks = repeated_tasks if repeated_tasks is not None else []
        self.closed = closed
        self.scheduled = scheduled
        self.deadline = deadline


def test_extract_timestamp_empty_node():
    """Test node with no timestamps returns empty list."""
    node = MockNode()
    timestamps = extract_timestamp(node)
    assert timestamps == []


def test_extract_timestamp_repeated_tasks_priority():
    """Test repeated DONE tasks take priority."""
    dt1 = datetime(2023, 10, 20, 14, 43)
    dt2 = datetime(2023, 10, 25, 10, 0)

    repeated = [MockRepeatedTask("DONE", dt1)]
    closed = MockTimestamp(dt2)
    node = MockNode(repeated_tasks=repeated, closed=closed)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt1


def test_extract_timestamp_repeated_tasks_all_done():
    """Test all DONE repeated tasks are returned."""
    dt1 = datetime(2023, 10, 20, 14, 43)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 18, 9, 15)

    repeated = [
        MockRepeatedTask("DONE", dt1),
        MockRepeatedTask("DONE", dt2),
        MockRepeatedTask("DONE", dt3),
    ]
    node = MockNode(repeated_tasks=repeated)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 3
    assert dt1 in timestamps
    assert dt2 in timestamps
    assert dt3 in timestamps


def test_extract_timestamp_repeated_tasks_mixed():
    """Test only DONE repeated tasks returned (not TODO)."""
    dt1 = datetime(2023, 10, 20, 14, 43)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 18, 9, 15)

    repeated = [
        MockRepeatedTask("DONE", dt1),
        MockRepeatedTask("TODO", dt2),
        MockRepeatedTask("DONE", dt3),
    ]
    node = MockNode(repeated_tasks=repeated)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 2
    assert dt1 in timestamps
    assert dt3 in timestamps
    assert dt2 not in timestamps


def test_extract_timestamp_repeated_tasks_empty():
    """Test falls back to closed when no DONE repeats."""
    dt_closed = datetime(2023, 10, 25, 10, 0)

    repeated = [MockRepeatedTask("TODO", datetime(2023, 10, 20, 14, 43))]
    closed = MockTimestamp(dt_closed)
    node = MockNode(repeated_tasks=repeated, closed=closed)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt_closed


def test_extract_timestamp_closed_fallback():
    """Test closed timestamp used when no repeated tasks."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(closed=closed)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt


def test_extract_timestamp_scheduled_fallback():
    """Test scheduled used when no closed timestamp."""
    dt = datetime(2023, 10, 20, 0, 0)
    scheduled = MockTimestamp(dt)
    node = MockNode(scheduled=scheduled)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt


def test_extract_timestamp_deadline_fallback():
    """Test deadline used when no scheduled timestamp."""
    dt = datetime(2023, 10, 25, 0, 0)
    deadline = MockTimestamp(dt)
    node = MockNode(deadline=deadline)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt


def test_extract_timestamp_priority_order():
    """Test that priority order is respected."""
    dt1 = datetime(2023, 10, 20, 14, 43)
    dt2 = datetime(2023, 10, 21, 10, 0)
    dt3 = datetime(2023, 10, 22, 0, 0)
    dt4 = datetime(2023, 10, 25, 0, 0)

    repeated = [MockRepeatedTask("DONE", dt1)]
    closed = MockTimestamp(dt2)
    scheduled = MockTimestamp(dt3)
    deadline = MockTimestamp(dt4)

    node = MockNode(repeated_tasks=repeated, closed=closed, scheduled=scheduled, deadline=deadline)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt1


def test_extract_timestamp_closed_none():
    """Test handles closed=None gracefully."""
    dt = datetime(2023, 10, 20, 0, 0)
    scheduled = MockTimestamp(dt)
    node = MockNode(closed=None, scheduled=scheduled)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt


def test_extract_timestamp_scheduled_none():
    """Test handles scheduled=None gracefully."""
    dt = datetime(2023, 10, 25, 0, 0)
    deadline = MockTimestamp(dt)
    node = MockNode(scheduled=None, deadline=deadline)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt


def test_extract_timestamp_deadline_none():
    """Test handles deadline=None gracefully."""
    node = MockNode(deadline=None)

    timestamps = extract_timestamp(node)

    assert timestamps == []


def test_extract_timestamp_returns_datetime_objects():
    """Test return type is datetime.datetime."""
    dt = datetime(2023, 10, 20, 14, 43)
    closed = MockTimestamp(dt)
    node = MockNode(closed=closed)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert isinstance(timestamps[0], datetime)


def test_extract_timestamp_date_only():
    """Test extraction with date-only timestamps."""
    dt = datetime(2023, 10, 20, 0, 0)
    scheduled = MockTimestamp(dt)
    node = MockNode(scheduled=scheduled)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt


def test_extract_timestamp_single_done_in_repeats():
    """Test single DONE task in repeated tasks."""
    dt = datetime(2023, 10, 20, 14, 43)
    repeated = [MockRepeatedTask("DONE", dt)]
    node = MockNode(repeated_tasks=repeated)

    timestamps = extract_timestamp(node)

    assert len(timestamps) == 1
    assert timestamps[0] == dt
