"""Tests for the compute_time_ranges() function."""

from datetime import datetime

from orgstats.core import TimeRange, compute_time_ranges


def test_compute_time_ranges_empty_items():
    """Test with empty items set."""
    items = set()
    time_ranges = {}
    timestamps = [datetime(2023, 10, 20, 14, 43)]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges == {}


def test_compute_time_ranges_empty_timestamps():
    """Test with empty timestamps list."""
    items = {"python"}
    time_ranges = {}
    timestamps = []

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges == {}


def test_compute_time_ranges_single_item_single_timestamp():
    """Test single item with single timestamp."""
    items = {"python"}
    time_ranges = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges
    assert time_ranges["python"].earliest == dt
    assert time_ranges["python"].latest == dt


def test_compute_time_ranges_single_item_multiple_timestamps():
    """Test single item with multiple timestamps."""
    items = {"python"}
    time_ranges = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2, dt3]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges
    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_multiple_items():
    """Test multiple items with same timestamps."""
    items = {"python", "testing", "debugging"}
    time_ranges = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2]

    compute_time_ranges(items, time_ranges, timestamps)

    assert len(time_ranges) == 3
    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt2
    assert time_ranges["testing"].earliest == dt1
    assert time_ranges["testing"].latest == dt2
    assert time_ranges["debugging"].earliest == dt1
    assert time_ranges["debugging"].latest == dt2


def test_compute_time_ranges_accumulates():
    """Test multiple calls accumulate correctly."""
    items1 = {"python"}
    items2 = {"python", "testing"}
    time_ranges = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)

    compute_time_ranges(items1, time_ranges, [dt1])
    compute_time_ranges(items2, time_ranges, [dt2])

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt2
    assert time_ranges["testing"].earliest == dt2
    assert time_ranges["testing"].latest == dt2


def test_compute_time_ranges_updates_existing():
    """Test updates existing TimeRange."""
    items = {"python"}
    dt1 = datetime(2023, 10, 19, 10, 0)
    dt2 = datetime(2023, 10, 18, 9, 15)
    dt3 = datetime(2023, 10, 20, 14, 43)
    time_ranges = {"python": TimeRange(earliest=dt1, latest=dt1)}

    compute_time_ranges(items, time_ranges, [dt2, dt3])

    assert time_ranges["python"].earliest == dt2
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_mutates_dict():
    """Test function modifies dict in-place."""
    items = {"python"}
    time_ranges = {}
    timestamps = [datetime(2023, 10, 20, 14, 43)]

    result = compute_time_ranges(items, time_ranges, timestamps)

    assert result is None
    assert "python" in time_ranges


def test_compute_time_ranges_chronological_order():
    """Test timestamps in chronological order."""
    items = {"python"}
    time_ranges = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2, dt3]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_reverse_order():
    """Test timestamps in reverse chronological order."""
    items = {"python"}
    time_ranges = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt3, dt2, dt1]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_mixed_order():
    """Test timestamps in mixed order."""
    items = {"python"}
    time_ranges = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt2, dt3, dt1]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_single_timestamp_list():
    """Test with single timestamp in list."""
    items = {"python", "testing"}
    time_ranges = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt
    assert time_ranges["python"].latest == dt
    assert time_ranges["testing"].earliest == dt
    assert time_ranges["testing"].latest == dt


def test_compute_time_ranges_normalized_tags():
    """Test with normalized tag names."""
    items = {"python", "testing", "devops"}
    time_ranges = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges
    assert "testing" in time_ranges
    assert "devops" in time_ranges
