"""Tests for timeline expansion function."""

from datetime import date

from orgstats.plot import expand_timeline


def test_expand_timeline_single_day() -> None:
    """Test expanding timeline when start and end are same day."""
    timeline = {date(2023, 10, 22): 5}
    result = expand_timeline(timeline, date(2023, 10, 22), date(2023, 10, 22))
    assert result == {date(2023, 10, 22): 5}


def test_expand_timeline_consecutive_days() -> None:
    """Test expanding timeline with no gaps in input."""
    timeline = {
        date(2023, 10, 22): 1,
        date(2023, 10, 23): 2,
        date(2023, 10, 24): 3,
    }
    result = expand_timeline(timeline, date(2023, 10, 22), date(2023, 10, 24))
    assert result == {
        date(2023, 10, 22): 1,
        date(2023, 10, 23): 2,
        date(2023, 10, 24): 3,
    }


def test_expand_timeline_with_gaps() -> None:
    """Test expanding timeline with missing days filled with 0."""
    timeline = {
        date(2023, 10, 22): 1,
        date(2023, 10, 26): 4,
    }
    result = expand_timeline(timeline, date(2023, 10, 22), date(2023, 10, 26))
    assert result == {
        date(2023, 10, 22): 1,
        date(2023, 10, 23): 0,
        date(2023, 10, 24): 0,
        date(2023, 10, 25): 0,
        date(2023, 10, 26): 4,
    }


def test_expand_timeline_multiple_weeks() -> None:
    """Test expanding timeline over a longer timespan."""
    timeline = {
        date(2023, 10, 1): 2,
        date(2023, 10, 15): 3,
        date(2023, 10, 31): 1,
    }
    result = expand_timeline(timeline, date(2023, 10, 1), date(2023, 10, 31))
    assert len(result) == 31
    assert result[date(2023, 10, 1)] == 2
    assert result[date(2023, 10, 2)] == 0
    assert result[date(2023, 10, 15)] == 3
    assert result[date(2023, 10, 31)] == 1


def test_expand_timeline_empty() -> None:
    """Test expanding empty timeline."""
    timeline: dict[date, int] = {}
    result = expand_timeline(timeline, date(2023, 10, 22), date(2023, 10, 26))
    assert result == {
        date(2023, 10, 22): 0,
        date(2023, 10, 23): 0,
        date(2023, 10, 24): 0,
        date(2023, 10, 25): 0,
        date(2023, 10, 26): 0,
    }


def test_expand_timeline_across_month_boundary() -> None:
    """Test expanding timeline across month boundaries."""
    timeline = {
        date(2023, 10, 30): 1,
        date(2023, 11, 2): 2,
    }
    result = expand_timeline(timeline, date(2023, 10, 30), date(2023, 11, 2))
    assert result == {
        date(2023, 10, 30): 1,
        date(2023, 10, 31): 0,
        date(2023, 11, 1): 0,
        date(2023, 11, 2): 2,
    }


def test_expand_timeline_preserves_all_values() -> None:
    """Test that expansion preserves all original values."""
    timeline = {
        date(2023, 10, 22): 1,
        date(2023, 10, 23): 0,
        date(2023, 10, 24): 5,
    }
    result = expand_timeline(timeline, date(2023, 10, 22), date(2023, 10, 24))
    assert result == timeline
