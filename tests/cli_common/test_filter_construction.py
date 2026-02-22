"""Tests for CLI filter construction and display logic."""

from dataclasses import dataclass


@dataclass
class FilterArgsStub:
    """Stub arguments for filter construction tests."""

    filter_gamify_exp_above: int | None = None
    filter_gamify_exp_below: int | None = None
    filter_repeats_above: int | None = None
    filter_repeats_below: int | None = None
    filter_date_from: str | None = None
    filter_date_until: str | None = None
    filter_properties: list[str] | None = None
    filter_tags: list[str] | None = None
    filter_headings: list[str] | None = None
    filter_bodies: list[str] | None = None
    filter_completed: bool = False
    filter_not_completed: bool = False


def make_args(**overrides: object) -> FilterArgsStub:
    """Build a FilterArgsStub with overrides."""
    args = FilterArgsStub()
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_handle_simple_filter_gamify_exp_above() -> None:
    """Test handle_simple_filter creates gamify_exp_above filter."""
    from org.cli_common import handle_simple_filter

    args = make_args(
        filter_gamify_exp_above=15,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
    )

    filters = handle_simple_filter("--filter-gamify-exp-above", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_simple_filter_gamify_exp_below() -> None:
    """Test handle_simple_filter creates gamify_exp_below filter."""
    from org.cli_common import handle_simple_filter

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=25,
        filter_repeats_above=None,
        filter_repeats_below=None,
    )

    filters = handle_simple_filter("--filter-gamify-exp-below", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_simple_filter_repeats_above() -> None:
    """Test handle_simple_filter creates repeats_above filter."""
    from org.cli_common import handle_simple_filter

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=5,
        filter_repeats_below=None,
    )

    filters = handle_simple_filter("--filter-repeats-above", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_simple_filter_repeats_below() -> None:
    """Test handle_simple_filter creates repeats_below filter."""
    from org.cli_common import handle_simple_filter

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=10,
    )

    filters = handle_simple_filter("--filter-repeats-below", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_simple_filter_no_match() -> None:
    """Test handle_simple_filter returns empty list when arg doesn't match."""
    from org.cli_common import handle_simple_filter

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
    )

    filters = handle_simple_filter("--filter-gamify-exp-above", args)

    assert len(filters) == 0


def test_handle_date_filter_from() -> None:
    """Test handle_date_filter creates date_from filter."""

    from org.cli_common import handle_date_filter

    args = make_args(filter_date_from="2025-01-01", filter_date_until=None)

    filters = handle_date_filter("--filter-date-from", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_date_filter_until() -> None:
    """Test handle_date_filter creates date_until filter."""
    from org.cli_common import handle_date_filter

    args = make_args(filter_date_from=None, filter_date_until="2025-12-31")

    filters = handle_date_filter("--filter-date-until", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_date_filter_no_match() -> None:
    """Test handle_date_filter returns empty list when arg doesn't match."""
    from org.cli_common import handle_date_filter

    args = make_args(filter_date_from=None, filter_date_until=None)

    filters = handle_date_filter("--filter-date-from", args)

    assert len(filters) == 0


def test_handle_completion_filter_completed() -> None:
    """Test handle_completion_filter creates completed filter."""
    from org.cli_common import handle_completion_filter

    args = make_args(filter_completed=True, filter_not_completed=False)

    filters = handle_completion_filter("--filter-completed", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_completion_filter_not_completed() -> None:
    """Test handle_completion_filter creates not_completed filter."""
    from org.cli_common import handle_completion_filter

    args = make_args(filter_completed=False, filter_not_completed=True)

    filters = handle_completion_filter("--filter-not-completed", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_completion_filter_no_match() -> None:
    """Test handle_completion_filter returns empty list when not set."""
    from org.cli_common import handle_completion_filter

    args = make_args(filter_completed=False, filter_not_completed=False)

    filters = handle_completion_filter("--filter-completed", args)

    assert len(filters) == 0


def test_handle_property_filter() -> None:
    """Test handle_property_filter creates property filter."""
    from org.cli_common import handle_property_filter

    filters = handle_property_filter("gamify_exp", "15")

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_tag_filter() -> None:
    """Test handle_tag_filter creates tag filter."""
    from org.cli_common import handle_tag_filter

    filters = handle_tag_filter("python")

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_create_filter_specs_multiple_filters() -> None:
    """Test create_filter_specs with multiple filter types."""
    from org.cli_common import create_filter_specs_from_args

    args = make_args(
        filter_gamify_exp_above=10,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from="2025-01-01",
        filter_date_until=None,
        filter_properties=["gamify_exp=15"],
        filter_tags=["python"],
        filter_headings=None,
        filter_bodies=None,
        filter_completed=True,
        filter_not_completed=False,
    )

    filter_order = [
        "--filter-gamify-exp-above",
        "--filter-date-from",
        "--filter-property",
        "--filter-tag",
        "--filter-completed",
    ]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) >= 4


def test_create_filter_specs_property_order() -> None:
    """Test create_filter_specs respects order of multiple property filters."""
    from org.cli_common import create_filter_specs_from_args

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=["gamify_exp=10", "gamify_exp=20"],
        filter_tags=None,
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    filter_order = ["--filter-property", "--filter-property"]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) == 2


def test_create_filter_specs_tag_order() -> None:
    """Test create_filter_specs respects order of multiple tag filters."""
    from org.cli_common import create_filter_specs_from_args

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=["python", "java"],
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    filter_order = ["--filter-tag", "--filter-tag"]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) == 2


def test_build_filter_chain() -> None:
    """Test build_filter_chain creates filter chain from args."""
    from org.cli_common import build_filter_chain

    args = make_args(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=["simple"],
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    argv = ["org", "stats", "summary", "--filter-tag", "simple", "file.org"]
    filters = build_filter_chain(args, argv)

    assert len(filters) == 1


def test_get_top_day_info_none() -> None:
    """Test get_top_day_info returns None when time_range is None."""
    from org.cli_common import get_top_day_info

    result = get_top_day_info(None)

    assert result is None


def test_get_top_day_info_empty_timeline() -> None:
    """Test get_top_day_info returns None when timeline is empty."""
    from org.analyze import TimeRange
    from org.cli_common import get_top_day_info

    time_range = TimeRange(earliest=None, latest=None, timeline={})
    result = get_top_day_info(time_range)

    assert result is None


def test_get_top_day_info_with_data() -> None:
    """Test get_top_day_info returns correct top day."""
    from datetime import date, datetime

    from org.analyze import TimeRange
    from org.cli_common import get_top_day_info

    timeline = {
        date(2025, 1, 1): 5,
        date(2025, 1, 2): 10,
        date(2025, 1, 3): 7,
    }
    time_range = TimeRange(
        earliest=datetime(2025, 1, 1), latest=datetime(2025, 1, 3), timeline=timeline
    )

    result = get_top_day_info(time_range)

    assert result is not None
    assert result[0] == "2025-01-02"
    assert result[1] == 10


def test_get_top_day_info_tie_uses_earliest() -> None:
    """Test get_top_day_info returns earliest date when there's a tie."""
    from datetime import date, datetime

    from org.analyze import TimeRange
    from org.cli_common import get_top_day_info

    timeline = {
        date(2025, 1, 3): 10,
        date(2025, 1, 1): 10,
        date(2025, 1, 2): 5,
    }
    time_range = TimeRange(
        earliest=datetime(2025, 1, 1), latest=datetime(2025, 1, 3), timeline=timeline
    )

    result = get_top_day_info(time_range)

    assert result is not None
    assert result[0] == "2025-01-01"
    assert result[1] == 10


def test_parse_filter_order_from_argv() -> None:
    """Test parse_filter_order_from_argv extracts filter args."""
    from org.cli_common import parse_filter_order_from_argv

    argv = [
        "org",
        "stats",
        "summary",
        "--filter-gamify-exp-above",
        "10",
        "--filter-tag",
        "work$",
        "file.org",
    ]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter-gamify-exp-above", "--filter-tag"]


def test_parse_filter_order_from_argv_no_filters() -> None:
    """Test parse_filter_order_from_argv with no filter args."""
    from org.cli_common import parse_filter_order_from_argv

    argv = ["org", "stats", "summary", "--max-results", "10", "file.org"]

    result = parse_filter_order_from_argv(argv)

    assert result == []


def test_parse_filter_order_from_argv_multiple_properties() -> None:
    """Test parse_filter_order_from_argv with multiple property filters."""
    from org.cli_common import parse_filter_order_from_argv

    argv = [
        "org",
        "stats",
        "summary",
        "--filter-property",
        "key1=val1",
        "--filter-property",
        "key2=val2",
        "file.org",
    ]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter-property", "--filter-property"]
