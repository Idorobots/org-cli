"""Tests for the TimeRange dataclass."""

from datetime import datetime

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
