"""Tests for compute helper functions."""

from datetime import datetime

from org.analyze import TimeRange, compute_avg_tasks_per_day, compute_max_single_day


def test_compute_max_single_day_empty_timerange() -> None:
    """Test with empty timerange."""
    timerange = TimeRange()

    max_day = compute_max_single_day(timerange)

    assert max_day == 0


def test_compute_max_single_day_single_day() -> None:
    """Test with single day."""
    timerange = TimeRange()
    dt = datetime(2023, 10, 20, 14, 43)
    timerange.update(dt)

    max_day = compute_max_single_day(timerange)

    assert max_day == 1


def test_compute_max_single_day_multiple_days() -> None:
    """Test with multiple days, different counts."""
    timerange = TimeRange()
    timerange.update(datetime(2023, 10, 18, 9, 15))
    timerange.update(datetime(2023, 10, 19, 10, 0))
    timerange.update(datetime(2023, 10, 20, 14, 43))
    timerange.update(datetime(2023, 10, 20, 15, 30))
    timerange.update(datetime(2023, 10, 20, 16, 45))

    max_day = compute_max_single_day(timerange)

    assert max_day == 3


def test_compute_avg_tasks_per_day_empty_timerange() -> None:
    """Test with empty timerange."""
    timerange = TimeRange()

    avg = compute_avg_tasks_per_day(timerange, 10)

    assert avg == 0.0


def test_compute_avg_tasks_per_day_zero_done_count() -> None:
    """Test with zero done count."""
    timerange = TimeRange()
    timerange.update(datetime(2023, 10, 20, 14, 43))

    avg = compute_avg_tasks_per_day(timerange, 0)

    assert avg == 0.0


def test_compute_avg_tasks_per_day_single_day() -> None:
    """Test with single day."""
    timerange = TimeRange()
    timerange.update(datetime(2023, 10, 20, 14, 43))

    avg = compute_avg_tasks_per_day(timerange, 5)

    assert avg == 5.0


def test_compute_avg_tasks_per_day_multiple_days() -> None:
    """Test with multiple days."""
    timerange = TimeRange()
    timerange.update(datetime(2023, 10, 18, 9, 15))
    timerange.update(datetime(2023, 10, 20, 14, 43))

    avg = compute_avg_tasks_per_day(timerange, 6)

    assert avg == 2.0


def test_compute_avg_tasks_per_day_fractional_result() -> None:
    """Test with fractional average."""
    timerange = TimeRange()
    timerange.update(datetime(2023, 10, 18, 9, 15))
    timerange.update(datetime(2023, 10, 20, 14, 43))

    avg = compute_avg_tasks_per_day(timerange, 5)

    assert avg == 5.0 / 3.0
