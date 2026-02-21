"""Tests for timeline bucketing function."""

from datetime import date

from org.plot import bucket_timeline


def test_bucket_timeline_evenly_divisible() -> None:
    """Test bucketing when days divide evenly into buckets."""
    timeline = {
        date(2023, 10, 1): 1,
        date(2023, 10, 2): 2,
        date(2023, 10, 3): 3,
        date(2023, 10, 4): 4,
        date(2023, 10, 5): 5,
        date(2023, 10, 6): 6,
    }
    result = bucket_timeline(timeline, 3)
    assert result == [3, 7, 11]


def test_bucket_timeline_with_remainder() -> None:
    """Test bucketing when days don't divide evenly."""
    timeline = {
        date(2023, 10, 1): 1,
        date(2023, 10, 2): 2,
        date(2023, 10, 3): 3,
        date(2023, 10, 4): 4,
        date(2023, 10, 5): 5,
    }
    result = bucket_timeline(timeline, 2)
    assert result == [6, 9]


def test_bucket_timeline_more_buckets_than_days() -> None:
    """Test when there are more buckets requested than days."""
    timeline = {
        date(2023, 10, 1): 5,
        date(2023, 10, 2): 10,
        date(2023, 10, 3): 15,
    }
    result = bucket_timeline(timeline, 10)
    assert len(result) == 10
    assert sum(result) == 30


def test_bucket_timeline_single_bucket() -> None:
    """Test when all days go into one bucket."""
    timeline = {
        date(2023, 10, 1): 1,
        date(2023, 10, 2): 2,
        date(2023, 10, 3): 3,
    }
    result = bucket_timeline(timeline, 1)
    assert result == [6]


def test_bucket_timeline_empty() -> None:
    """Test bucketing empty timeline."""
    timeline: dict[date, int] = {}
    result = bucket_timeline(timeline, 5)
    assert result == [0, 0, 0, 0, 0]


def test_bucket_timeline_sums_correctly() -> None:
    """Test that sum of buckets equals sum of input."""
    timeline = {
        date(2023, 10, 1): 10,
        date(2023, 10, 2): 20,
        date(2023, 10, 3): 30,
        date(2023, 10, 4): 40,
        date(2023, 10, 5): 50,
    }
    result = bucket_timeline(timeline, 3)
    assert sum(result) == sum(timeline.values())


def test_bucket_timeline_single_day() -> None:
    """Test bucketing a single day across multiple buckets."""
    timeline = {date(2023, 10, 1): 10}
    result = bucket_timeline(timeline, 5)
    assert result[0] == 10
    assert sum(result) == 10


def test_bucket_timeline_zeros_included() -> None:
    """Test that days with zero activity are handled correctly."""
    timeline = {
        date(2023, 10, 1): 5,
        date(2023, 10, 2): 0,
        date(2023, 10, 3): 0,
        date(2023, 10, 4): 10,
    }
    result = bucket_timeline(timeline, 2)
    assert result == [5, 10]


def test_bucket_timeline_large_number_of_days() -> None:
    """Test bucketing a large timeline into fewer buckets."""
    timeline = {date(2023, 1, 1) + __import__("datetime").timedelta(days=i): i for i in range(100)}
    result = bucket_timeline(timeline, 10)
    assert len(result) == 10
    assert sum(result) == sum(range(100))


def test_bucket_timeline_uneven_distribution() -> None:
    """Test that bucketing distributes items as evenly as possible."""
    timeline = {date(2023, 10, 1) + __import__("datetime").timedelta(days=i): 1 for i in range(10)}
    result = bucket_timeline(timeline, 3)
    assert len(result) == 3
    assert sum(result) == 10
