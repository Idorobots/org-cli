"""Tests for the compute_time_ranges() function."""

from datetime import date, datetime

from orgstats.core import TimeRange, compute_time_ranges


def test_compute_time_ranges_empty_items() -> None:
    """Test with empty items set."""
    items: set[str] = set()
    time_ranges: dict[str, TimeRange] = {}
    timestamps = [datetime(2023, 10, 20, 14, 43)]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges == {}


def test_compute_time_ranges_empty_timestamps() -> None:
    """Test with empty timestamps list."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    timestamps: list[datetime] = []

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges == {}


def test_compute_time_ranges_single_item_single_timestamp() -> None:
    """Test single item with single timestamp."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges
    assert time_ranges["python"].earliest == dt
    assert time_ranges["python"].latest == dt


def test_compute_time_ranges_single_item_multiple_timestamps() -> None:
    """Test single item with multiple timestamps."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2, dt3]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges
    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_multiple_items() -> None:
    """Test multiple items with same timestamps."""
    items = {"python", "testing", "debugging"}
    time_ranges: dict[str, TimeRange] = {}
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


def test_compute_time_ranges_accumulates() -> None:
    """Test multiple calls accumulate correctly."""
    items1 = {"python"}
    items2 = {"python", "testing"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)

    compute_time_ranges(items1, time_ranges, [dt1])
    compute_time_ranges(items2, time_ranges, [dt2])

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt2
    assert time_ranges["testing"].earliest == dt2
    assert time_ranges["testing"].latest == dt2


def test_compute_time_ranges_updates_existing() -> None:
    """Test updates existing TimeRange."""
    items = {"python"}
    dt1 = datetime(2023, 10, 19, 10, 0)
    dt2 = datetime(2023, 10, 18, 9, 15)
    dt3 = datetime(2023, 10, 20, 14, 43)
    time_ranges = {"python": TimeRange(earliest=dt1, latest=dt1)}

    compute_time_ranges(items, time_ranges, [dt2, dt3])

    assert time_ranges["python"].earliest == dt2
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_mutates_dict() -> None:
    """Test function modifies dict in-place."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    timestamps = [datetime(2023, 10, 20, 14, 43)]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges


def test_compute_time_ranges_chronological_order() -> None:
    """Test timestamps in chronological order."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2, dt3]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_reverse_order() -> None:
    """Test timestamps in reverse chronological order."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt3, dt2, dt1]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_mixed_order() -> None:
    """Test timestamps in mixed order."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt2, dt3, dt1]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt1
    assert time_ranges["python"].latest == dt3


def test_compute_time_ranges_single_timestamp_list() -> None:
    """Test with single timestamp in list."""
    items = {"python", "testing"}
    time_ranges: dict[str, TimeRange] = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    assert time_ranges["python"].earliest == dt
    assert time_ranges["python"].latest == dt
    assert time_ranges["testing"].earliest == dt
    assert time_ranges["testing"].latest == dt


def test_compute_time_ranges_normalized_tags() -> None:
    """Test with normalized tag names."""
    items = {"python", "testing", "devops"}
    time_ranges: dict[str, TimeRange] = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    assert "python" in time_ranges
    assert "testing" in time_ranges
    assert "devops" in time_ranges


def test_compute_time_ranges_timeline_single_timestamp() -> None:
    """Test single timestamp creates timeline entry."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt]

    compute_time_ranges(items, time_ranges, timestamps)

    timeline = time_ranges["python"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_compute_time_ranges_timeline_multiple_timestamps() -> None:
    """Test multiple timestamps on different days create multiple timeline entries."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2, dt3]

    compute_time_ranges(items, time_ranges, timestamps)

    timeline = time_ranges["python"].timeline
    assert len(timeline) == 3
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_compute_time_ranges_timeline_same_day_timestamps() -> None:
    """Test multiple timestamps on same day increment counter."""
    items = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 20, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    timestamps = [dt1, dt2]

    compute_time_ranges(items, time_ranges, timestamps)

    timeline = time_ranges["python"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 2


def test_compute_time_ranges_timeline_accumulates() -> None:
    """Test multiple calls accumulate timeline correctly."""
    items1 = {"python"}
    items2 = {"python"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 18, 14, 30)
    dt3 = datetime(2023, 10, 19, 10, 0)

    compute_time_ranges(items1, time_ranges, [dt1])
    compute_time_ranges(items2, time_ranges, [dt2, dt3])

    timeline = time_ranges["python"].timeline
    assert len(timeline) == 2
    assert timeline[date(2023, 10, 18)] == 2
    assert timeline[date(2023, 10, 19)] == 1


def test_compute_time_ranges_timeline_multiple_items() -> None:
    """Test multiple items all get timeline entries."""
    items = {"python", "testing"}
    time_ranges: dict[str, TimeRange] = {}
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    timestamps = [dt1, dt2]

    compute_time_ranges(items, time_ranges, timestamps)

    python_timeline = time_ranges["python"].timeline
    testing_timeline = time_ranges["testing"].timeline

    assert len(python_timeline) == 2
    assert python_timeline[date(2023, 10, 18)] == 1
    assert python_timeline[date(2023, 10, 19)] == 1

    assert len(testing_timeline) == 2
    assert testing_timeline[date(2023, 10, 18)] == 1
    assert testing_timeline[date(2023, 10, 19)] == 1
