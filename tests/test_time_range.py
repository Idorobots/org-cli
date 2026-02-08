"""Tests for the TimeRange dataclass."""

from datetime import date, datetime

from orgstats.core import TimeRange


def test_time_range_initialization():
    """Test TimeRange initializes with None values."""
    time_range = TimeRange()

    assert time_range.earliest is None
    assert time_range.latest is None


def test_time_range_initialization_with_values():
    """Test TimeRange with provided values."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    time_range = TimeRange(earliest=dt1, latest=dt2)

    assert time_range.earliest == dt1
    assert time_range.latest == dt2


def test_time_range_update_first_timestamp():
    """Test updating empty TimeRange with first timestamp."""
    time_range = TimeRange()
    dt = datetime(2023, 10, 19, 10, 0)

    time_range.update(dt)

    assert time_range.earliest == dt
    assert time_range.latest == dt


def test_time_range_update_earlier_timestamp():
    """Test updating TimeRange with earlier timestamp."""
    dt1 = datetime(2023, 10, 19, 10, 0)
    dt2 = datetime(2023, 10, 18, 9, 15)
    time_range = TimeRange(earliest=dt1, latest=dt1)

    time_range.update(dt2)

    assert time_range.earliest == dt2
    assert time_range.latest == dt1


def test_time_range_update_later_timestamp():
    """Test updating TimeRange with later timestamp."""
    dt1 = datetime(2023, 10, 19, 10, 0)
    dt2 = datetime(2023, 10, 20, 14, 43)
    time_range = TimeRange(earliest=dt1, latest=dt1)

    time_range.update(dt2)

    assert time_range.earliest == dt1
    assert time_range.latest == dt2


def test_time_range_update_middle_timestamp():
    """Test timestamp between earliest and latest doesn't change range."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)
    time_range = TimeRange(earliest=dt1, latest=dt3)

    time_range.update(dt2)

    assert time_range.earliest == dt1
    assert time_range.latest == dt3


def test_time_range_update_same_timestamp():
    """Test updating with same timestamp multiple times."""
    dt = datetime(2023, 10, 19, 10, 0)
    time_range = TimeRange()

    time_range.update(dt)
    time_range.update(dt)
    time_range.update(dt)

    assert time_range.earliest == dt
    assert time_range.latest == dt


def test_time_range_repr():
    """Test string representation."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    time_range = TimeRange(earliest=dt1, latest=dt2)

    repr_str = repr(time_range)
    assert "TimeRange" in repr_str
    assert "earliest" in repr_str
    assert "latest" in repr_str


def test_time_range_is_dataclass():
    """Test that TimeRange is a dataclass."""
    from dataclasses import is_dataclass

    assert is_dataclass(TimeRange)


def test_time_range_equality():
    """Test equality comparison."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)

    time_range1 = TimeRange(earliest=dt1, latest=dt2)
    time_range2 = TimeRange(earliest=dt1, latest=dt2)
    time_range3 = TimeRange(earliest=dt1, latest=None)

    assert time_range1 == time_range2
    assert time_range1 != time_range3


def test_time_range_multiple_updates():
    """Test multiple updates with various timestamps."""
    time_range = TimeRange()

    dt1 = datetime(2023, 10, 20, 14, 43)
    dt2 = datetime(2023, 10, 18, 9, 15)
    dt3 = datetime(2023, 10, 19, 10, 0)
    dt4 = datetime(2023, 10, 21, 16, 30)

    time_range.update(dt1)
    time_range.update(dt2)
    time_range.update(dt3)
    time_range.update(dt4)

    assert time_range.earliest == dt2
    assert time_range.latest == dt4


def test_time_range_timeline_initialized_empty():
    """Test TimeRange timeline initializes as empty dict."""
    time_range = TimeRange()

    assert time_range.timeline == {}


def test_time_range_timeline_single_occurrence():
    """Test single timestamp creates one timeline entry with count=1."""
    time_range = TimeRange()
    dt = datetime(2023, 10, 19, 10, 0)

    time_range.update(dt)

    assert len(time_range.timeline) == 1
    assert time_range.timeline[date(2023, 10, 19)] == 1


def test_time_range_timeline_same_day_different_times():
    """Test two timestamps on same day increment the same counter."""
    time_range = TimeRange()
    dt1 = datetime(2023, 10, 19, 10, 0)
    dt2 = datetime(2023, 10, 19, 15, 30)

    time_range.update(dt1)
    time_range.update(dt2)

    assert len(time_range.timeline) == 1
    assert time_range.timeline[date(2023, 10, 19)] == 2


def test_time_range_timeline_multiple_days():
    """Test timestamps on different days create separate timeline entries."""
    time_range = TimeRange()
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 20, 14, 43)

    time_range.update(dt1)
    time_range.update(dt2)
    time_range.update(dt3)

    assert len(time_range.timeline) == 3
    assert time_range.timeline[date(2023, 10, 18)] == 1
    assert time_range.timeline[date(2023, 10, 19)] == 1
    assert time_range.timeline[date(2023, 10, 20)] == 1


def test_time_range_timeline_repeated_same_day():
    """Test multiple updates with same timestamp increments counter."""
    time_range = TimeRange()
    dt = datetime(2023, 10, 19, 10, 0)

    time_range.update(dt)
    time_range.update(dt)
    time_range.update(dt)

    assert len(time_range.timeline) == 1
    assert time_range.timeline[date(2023, 10, 19)] == 3


def test_time_range_timeline_mixed_days():
    """Test mix of same-day and different-day occurrences."""
    time_range = TimeRange()
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 18, 14, 30)
    dt3 = datetime(2023, 10, 19, 10, 0)
    dt4 = datetime(2023, 10, 20, 8, 0)
    dt5 = datetime(2023, 10, 20, 16, 45)

    time_range.update(dt1)
    time_range.update(dt2)
    time_range.update(dt3)
    time_range.update(dt4)
    time_range.update(dt5)

    assert len(time_range.timeline) == 3
    assert time_range.timeline[date(2023, 10, 18)] == 2
    assert time_range.timeline[date(2023, 10, 19)] == 1
    assert time_range.timeline[date(2023, 10, 20)] == 2


def test_time_range_timeline_not_in_repr():
    """Test timeline is not included in string representation."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    time_range = TimeRange(earliest=dt1, latest=dt2)
    time_range.update(dt1)
    time_range.update(dt2)

    repr_str = repr(time_range)
    assert "TimeRange" in repr_str
    assert "earliest" in repr_str
    assert "latest" in repr_str
    assert "timeline" not in repr_str


def test_time_range_repr_includes_top_day():
    """Test that repr includes top_day field."""
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    time_range = TimeRange(earliest=dt1, latest=dt2)
    time_range.update(dt1)
    time_range.update(dt2)

    repr_str = repr(time_range)
    assert "top_day=" in repr_str
    assert "earliest=" in repr_str
    assert "latest=" in repr_str


def test_time_range_top_day_single_occurrence():
    """Test top_day with single occurrence."""
    time_range = TimeRange()
    dt = datetime(2023, 10, 19, 10, 0)
    time_range.update(dt)

    repr_str = repr(time_range)
    assert "top_day='2023-10-19'" in repr_str


def test_time_range_top_day_multiple_equal_counts():
    """Test top_day selects earliest date when multiple days have same count."""
    time_range = TimeRange()
    dt1 = datetime(2023, 10, 20, 9, 15)
    dt2 = datetime(2023, 10, 18, 10, 0)
    dt3 = datetime(2023, 10, 19, 14, 30)

    time_range.update(dt1)
    time_range.update(dt2)
    time_range.update(dt3)

    repr_str = repr(time_range)
    assert "top_day='2023-10-18'" in repr_str


def test_time_range_top_day_highest_count():
    """Test top_day selects day with highest count."""
    time_range = TimeRange()
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 19, 10, 0)
    dt3 = datetime(2023, 10, 19, 15, 30)
    dt4 = datetime(2023, 10, 20, 8, 0)

    time_range.update(dt1)
    time_range.update(dt2)
    time_range.update(dt3)
    time_range.update(dt4)

    repr_str = repr(time_range)
    assert "top_day='2023-10-19'" in repr_str


def test_time_range_top_day_empty_timeline():
    """Test top_day is None when timeline is empty."""
    time_range = TimeRange()

    repr_str = repr(time_range)
    assert "top_day=None" in repr_str
    assert "earliest=None" in repr_str
    assert "latest=None" in repr_str
