"""Tests for the _combine_time_ranges() function."""

from datetime import date, datetime

from orgstats.analyze import TimeRange, _combine_time_ranges


def test_combine_time_ranges_empty_list() -> None:
    """Test _combine_time_ranges with empty tag list."""
    tag_time_ranges: dict[str, TimeRange] = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3, date(2023, 1, 5): 2},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, [])

    assert result.earliest is None
    assert result.latest is None
    assert result.timeline == {}


def test_combine_time_ranges_single_tag() -> None:
    """Test _combine_time_ranges with a single tag."""
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3, date(2023, 1, 5): 2},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["python"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 1, 5)
    assert result.timeline == {date(2023, 1, 1): 3, date(2023, 1, 5): 2}


def test_combine_time_ranges_two_tags_non_overlapping() -> None:
    """Test _combine_time_ranges with two tags having non-overlapping dates."""
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3, date(2023, 1, 5): 2},
        ),
        "java": TimeRange(
            earliest=datetime(2023, 2, 1),
            latest=datetime(2023, 2, 10),
            timeline={date(2023, 2, 1): 5, date(2023, 2, 10): 1},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["python", "java"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 2, 10)
    assert result.timeline == {
        date(2023, 1, 1): 3,
        date(2023, 1, 5): 2,
        date(2023, 2, 1): 5,
        date(2023, 2, 10): 1,
    }


def test_combine_time_ranges_two_tags_overlapping_dates() -> None:
    """Test _combine_time_ranges with two tags having overlapping dates."""
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3, date(2023, 1, 3): 2, date(2023, 1, 5): 1},
        ),
        "testing": TimeRange(
            earliest=datetime(2023, 1, 3),
            latest=datetime(2023, 1, 7),
            timeline={date(2023, 1, 3): 4, date(2023, 1, 5): 2, date(2023, 1, 7): 1},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["python", "testing"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 1, 7)
    assert result.timeline == {
        date(2023, 1, 1): 3,
        date(2023, 1, 3): 6,
        date(2023, 1, 5): 3,
        date(2023, 1, 7): 1,
    }


def test_combine_time_ranges_tag_not_in_dict() -> None:
    """Test _combine_time_ranges with tag not present in dict."""
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["python", "missing_tag"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 1, 5)
    assert result.timeline == {date(2023, 1, 1): 3}


def test_combine_time_ranges_mixed_present_and_missing() -> None:
    """Test _combine_time_ranges with mix of present and missing tags."""
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3},
        ),
        "java": TimeRange(
            earliest=datetime(2023, 2, 1),
            latest=datetime(2023, 2, 10),
            timeline={date(2023, 2, 1): 5},
        ),
    }
    result = _combine_time_ranges(
        tag_time_ranges, ["missing1", "python", "missing2", "java", "missing3"]
    )

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 2, 10)
    assert result.timeline == {date(2023, 1, 1): 3, date(2023, 2, 1): 5}


def test_combine_time_ranges_earliest_latest_tracking() -> None:
    """Test that earliest and latest are correctly tracked across multiple tags."""
    tag_time_ranges = {
        "tag1": TimeRange(
            earliest=datetime(2023, 5, 15),
            latest=datetime(2023, 6, 1),
            timeline={date(2023, 5, 15): 1},
        ),
        "tag2": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 3, 1),
            timeline={date(2023, 1, 1): 1},
        ),
        "tag3": TimeRange(
            earliest=datetime(2023, 7, 1),
            latest=datetime(2023, 12, 31),
            timeline={date(2023, 12, 31): 1},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["tag1", "tag2", "tag3"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 12, 31)
    assert result.timeline == {
        date(2023, 1, 1): 1,
        date(2023, 5, 15): 1,
        date(2023, 12, 31): 1,
    }


def test_combine_time_ranges_all_tags_missing_data() -> None:
    """Test _combine_time_ranges when all tags are missing from dict."""
    tag_time_ranges: dict[str, TimeRange] = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["missing1", "missing2", "missing3"])

    assert result.earliest is None
    assert result.latest is None
    assert result.timeline == {}


def test_combine_time_ranges_tag_with_empty_timeline() -> None:
    """Test _combine_time_ranges with tag having no timeline data."""
    tag_time_ranges = {
        "python": TimeRange(earliest=None, latest=None, timeline={}),
        "java": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 5),
            timeline={date(2023, 1, 1): 3},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["python", "java"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 1, 5)
    assert result.timeline == {date(2023, 1, 1): 3}


def test_combine_time_ranges_multiple_overlapping_same_date() -> None:
    """Test summing counts when multiple tags have same dates."""
    tag_time_ranges = {
        "tag1": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 1),
            timeline={date(2023, 1, 1): 10},
        ),
        "tag2": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 1),
            timeline={date(2023, 1, 1): 20},
        ),
        "tag3": TimeRange(
            earliest=datetime(2023, 1, 1),
            latest=datetime(2023, 1, 1),
            timeline={date(2023, 1, 1): 5},
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["tag1", "tag2", "tag3"])

    assert result.earliest == datetime(2023, 1, 1)
    assert result.latest == datetime(2023, 1, 1)
    assert result.timeline == {date(2023, 1, 1): 35}


def test_combine_time_ranges_complex_scenario() -> None:
    """Test complex scenario with multiple tags, overlaps, and gaps."""
    tag_time_ranges = {
        "python": TimeRange(
            earliest=datetime(2023, 1, 1, 10, 0),
            latest=datetime(2023, 1, 10, 15, 30),
            timeline={
                date(2023, 1, 1): 5,
                date(2023, 1, 5): 3,
                date(2023, 1, 10): 2,
            },
        ),
        "testing": TimeRange(
            earliest=datetime(2023, 1, 5, 8, 0),
            latest=datetime(2023, 1, 15, 12, 0),
            timeline={
                date(2023, 1, 5): 7,
                date(2023, 1, 10): 4,
                date(2023, 1, 15): 1,
            },
        ),
        "debugging": TimeRange(
            earliest=datetime(2022, 12, 25, 23, 59),
            latest=datetime(2023, 1, 3, 1, 0),
            timeline={
                date(2022, 12, 25): 2,
                date(2023, 1, 1): 1,
                date(2023, 1, 3): 3,
            },
        ),
    }
    result = _combine_time_ranges(tag_time_ranges, ["python", "testing", "debugging"])

    assert result.earliest == datetime(2022, 12, 25, 23, 59)
    assert result.latest == datetime(2023, 1, 15, 12, 0)
    assert result.timeline == {
        date(2022, 12, 25): 2,
        date(2023, 1, 1): 6,
        date(2023, 1, 3): 3,
        date(2023, 1, 5): 10,
        date(2023, 1, 10): 6,
        date(2023, 1, 15): 1,
    }
