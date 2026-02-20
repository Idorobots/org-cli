"""Tests for CLI filter construction and display logic."""

import argparse
import os
import subprocess
import sys
from io import StringIO


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_handle_preset_filter_simple() -> None:
    """Test that 'simple' preset expands to gamify_exp < 10 filter."""
    from orgstats.cli import handle_preset_filter

    filters = handle_preset_filter("simple")

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_preset_filter_regular() -> None:
    """Test that 'regular' preset expands to two filters."""
    from orgstats.cli import handle_preset_filter

    filters = handle_preset_filter("regular")

    assert len(filters) == 2
    assert filters[0].filter is not None
    assert filters[1].filter is not None


def test_handle_preset_filter_hard() -> None:
    """Test that 'hard' preset expands to gamify_exp >= 20 filter."""
    from orgstats.cli import handle_preset_filter

    filters = handle_preset_filter("hard")

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_preset_filter_all() -> None:
    """Test that 'all' preset returns empty list."""
    from orgstats.cli import handle_preset_filter

    filters = handle_preset_filter("all")

    assert len(filters) == 0
    assert filters == []


def test_handle_simple_filter_gamify_exp_above() -> None:
    """Test handle_simple_filter creates gamify_exp_above filter."""
    from orgstats.cli import handle_simple_filter

    args = argparse.Namespace(
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
    from orgstats.cli import handle_simple_filter

    args = argparse.Namespace(
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
    from orgstats.cli import handle_simple_filter

    args = argparse.Namespace(
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
    from orgstats.cli import handle_simple_filter

    args = argparse.Namespace(
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
    from orgstats.cli import handle_simple_filter

    args = argparse.Namespace(
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
    )

    filters = handle_simple_filter("--filter-gamify-exp-above", args)

    assert len(filters) == 0


def test_handle_date_filter_from() -> None:
    """Test handle_date_filter creates date_from filter."""

    from orgstats.cli import handle_date_filter

    args = argparse.Namespace(filter_date_from="2025-01-01", filter_date_until=None)

    filters = handle_date_filter("--filter-date-from", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_date_filter_until() -> None:
    """Test handle_date_filter creates date_until filter."""
    from orgstats.cli import handle_date_filter

    args = argparse.Namespace(filter_date_from=None, filter_date_until="2025-12-31")

    filters = handle_date_filter("--filter-date-until", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_date_filter_no_match() -> None:
    """Test handle_date_filter returns empty list when arg doesn't match."""
    from orgstats.cli import handle_date_filter

    args = argparse.Namespace(filter_date_from=None, filter_date_until=None)

    filters = handle_date_filter("--filter-date-from", args)

    assert len(filters) == 0


def test_handle_completion_filter_completed() -> None:
    """Test handle_completion_filter creates completed filter."""
    from orgstats.cli import handle_completion_filter

    args = argparse.Namespace(filter_completed=True, filter_not_completed=False)

    filters = handle_completion_filter("--filter-completed", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_completion_filter_not_completed() -> None:
    """Test handle_completion_filter creates not_completed filter."""
    from orgstats.cli import handle_completion_filter

    args = argparse.Namespace(filter_completed=False, filter_not_completed=True)

    filters = handle_completion_filter("--filter-not-completed", args)

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_completion_filter_no_match() -> None:
    """Test handle_completion_filter returns empty list when not set."""
    from orgstats.cli import handle_completion_filter

    args = argparse.Namespace(filter_completed=False, filter_not_completed=False)

    filters = handle_completion_filter("--filter-completed", args)

    assert len(filters) == 0


def test_handle_property_filter() -> None:
    """Test handle_property_filter creates property filter."""
    from orgstats.cli import handle_property_filter

    filters = handle_property_filter("gamify_exp", "15")

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_handle_tag_filter() -> None:
    """Test handle_tag_filter creates tag filter."""
    from orgstats.cli import handle_tag_filter

    filters = handle_tag_filter("python")

    assert len(filters) == 1
    assert filters[0].filter is not None


def test_create_filter_specs_simple_preset() -> None:
    """Test create_filter_specs with simple preset."""
    from orgstats.cli import create_filter_specs_from_args

    args = argparse.Namespace(
        filter="simple",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    filter_order = ["--filter"]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) == 1


def test_create_filter_specs_regular_preset() -> None:
    """Test create_filter_specs with regular preset."""
    from orgstats.cli import create_filter_specs_from_args

    args = argparse.Namespace(
        filter="regular",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    filter_order = ["--filter"]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) == 2


def test_create_filter_specs_multiple_filters() -> None:
    """Test create_filter_specs with multiple filter types."""
    from orgstats.cli import create_filter_specs_from_args

    args = argparse.Namespace(
        filter="all",
        filter_gamify_exp_above=10,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from="2025-01-01",
        filter_date_until=None,
        filter_properties=["gamify_exp=15"],
        filter_tags=["python"],
        filter_completed=True,
        filter_not_completed=False,
    )

    filter_order = [
        "--filter",
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
    from orgstats.cli import create_filter_specs_from_args

    args = argparse.Namespace(
        filter="all",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=["gamify_exp=10", "gamify_exp=20"],
        filter_tags=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    filter_order = ["--filter-property", "--filter-property"]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) == 2


def test_create_filter_specs_tag_order() -> None:
    """Test create_filter_specs respects order of multiple tag filters."""
    from orgstats.cli import create_filter_specs_from_args

    args = argparse.Namespace(
        filter="all",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=["python", "java"],
        filter_completed=False,
        filter_not_completed=False,
    )

    filter_order = ["--filter-tag", "--filter-tag"]
    filters = create_filter_specs_from_args(args, filter_order)

    assert len(filters) == 2


def test_build_filter_chain() -> None:
    """Test build_filter_chain creates filter chain from args."""
    from orgstats.cli import build_filter_chain

    args = argparse.Namespace(
        filter="simple",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_completed=False,
        filter_not_completed=False,
    )

    argv = ["orgstats", "--filter", "simple", "file.org"]
    filters = build_filter_chain(args, argv)

    assert len(filters) == 1


def test_get_top_day_info_none() -> None:
    """Test get_top_day_info returns None when time_range is None."""
    from orgstats.cli import get_top_day_info

    result = get_top_day_info(None)

    assert result is None


def test_get_top_day_info_empty_timeline() -> None:
    """Test get_top_day_info returns None when timeline is empty."""
    from orgstats.analyze import TimeRange
    from orgstats.cli import get_top_day_info

    time_range = TimeRange(earliest=None, latest=None, timeline={})
    result = get_top_day_info(time_range)

    assert result is None


def test_get_top_day_info_with_data() -> None:
    """Test get_top_day_info returns correct top day."""
    from datetime import date, datetime

    from orgstats.analyze import TimeRange
    from orgstats.cli import get_top_day_info

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

    from orgstats.analyze import TimeRange
    from orgstats.cli import get_top_day_info

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


def test_display_category() -> None:
    """Test display_category outputs formatted results."""
    from orgstats.analyze import Frequency, Relations, TimeRange
    from orgstats.cli import display_category

    frequencies = {"python": Frequency(total=10), "java": Frequency(total=8)}
    time_ranges: dict[str, TimeRange] = {}
    exclude_set: set[str] = set()
    relations_dict: dict[str, Relations] = {}

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_category(
            "test tags",
            (frequencies, time_ranges, exclude_set, relations_dict),
            (10, 3, 50, None, None, TimeRange()),
            lambda item: -item[1].total,
            10,
        )

        output = sys.stdout.getvalue()

        assert "Top test tags:" in output
        assert "python" in output
        assert "java" in output
        assert "python (10)" in output
        assert "java (8)" in output

    finally:
        sys.stdout = original_stdout


def test_display_category_with_time_ranges() -> None:
    """Test display_category includes time range information."""
    from datetime import datetime

    from orgstats.analyze import Frequency, Relations, TimeRange
    from orgstats.cli import display_category

    frequencies = {"python": Frequency(total=10)}
    time_ranges = {
        "python": TimeRange(
            earliest=datetime(2025, 1, 1), latest=datetime(2025, 1, 31), timeline={}
        )
    }
    exclude_set: set[str] = set()
    relations_dict: dict[str, Relations] = {}

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_category(
            "test tags",
            (frequencies, time_ranges, exclude_set, relations_dict),
            (10, 3, 50, None, None, TimeRange()),
            lambda item: -item[1].total,
            10,
        )

        output = sys.stdout.getvalue()

        assert "python (10)" in output

    finally:
        sys.stdout = original_stdout


def test_display_category_with_relations() -> None:
    """Test display_category includes relations."""
    from orgstats.analyze import Frequency, Relations, TimeRange
    from orgstats.cli import display_category

    frequencies = {"python": Frequency(total=10)}
    time_ranges: dict[str, TimeRange] = {}
    exclude_set: set[str] = set()
    relations_dict = {"python": Relations(name="python", relations={"django": 5, "flask": 3})}

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_category(
            "test tags",
            (frequencies, time_ranges, exclude_set, relations_dict),
            (10, 3, 50, None, None, TimeRange()),
            lambda item: -item[1].total,
            10,
        )

        output = sys.stdout.getvalue()

        assert "django (5)" in output
        assert "flask (3)" in output

    finally:
        sys.stdout = original_stdout


def test_display_category_with_max_items_zero() -> None:
    """Test display_category with max_items=0 omits section entirely."""
    from orgstats.analyze import Frequency, Relations, TimeRange
    from orgstats.cli import display_category

    frequencies = {"python": Frequency(total=10), "java": Frequency(total=8)}
    time_ranges: dict[str, TimeRange] = {}
    exclude_set: set[str] = set()
    relations_dict: dict[str, Relations] = {}

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_category(
            "test tags",
            (frequencies, time_ranges, exclude_set, relations_dict),
            (10, 3, 50, None, None, TimeRange()),
            lambda item: -item[1].total,
            0,
        )

        output = sys.stdout.getvalue()

        assert output == ""
        assert "Top test tags:" not in output

    finally:
        sys.stdout = original_stdout


def test_display_results_with_tag_groups() -> None:
    """Test display_results shows tag groups."""
    from io import StringIO

    from orgstats.analyze import (
        AnalysisResult,
        Frequency,
        Group,
        TimeRange,
    )
    from orgstats.cli import display_results
    from orgstats.histogram import Histogram

    tag_groups = [Group(tags=["python", "programming", "coding"], time_range=TimeRange())]

    result = AnalysisResult(
        total_tasks=3,
        task_states=Histogram(values={"DONE": 3}),
        task_categories=Histogram(values={}),
        task_days=Histogram(values={"Monday": 3}),
        tags={

            "python": Tag(

                name="python",

                frequency=Frequency(total=3),

                relations=Relations(name="python", relations={}),

                time_range=TimeRange(),

                total_tasks=3,

                avg_tasks_per_day=0.0,

                max_single_day_count=0,

            )

        },
        timerange=TimeRange(earliest=None, latest=None, timeline={}),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_groups=tag_groups,
    )

    args = argparse.Namespace(
        show="tags",
        max_results=10,
        max_tags=5,
        max_relations=3,
        min_group_size=3,
        max_groups=5,
        buckets=50,
    )

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_results(result, [], args, (set(), None, None, ["DONE"], ["TODO"]))

        output = sys.stdout.getvalue()

        assert "Tag groups:" in output
        assert "python, programming, coding" in output

    finally:
        sys.stdout = original_stdout


def test_display_results_tag_groups_filtered_by_min_size() -> None:
    """Test display_results filters tag groups by min_group_size."""
    from io import StringIO

    from orgstats.analyze import (
        AnalysisResult,
        Frequency,
        Group,
        TimeRange,
    )
    from orgstats.cli import display_results
    from orgstats.histogram import Histogram

    tag_groups = [
        Group(tags=["python", "programming"], time_range=TimeRange()),
        Group(tags=["java", "programming", "coding"], time_range=TimeRange()),
    ]

    result = AnalysisResult(
        total_tasks=5,
        task_states=Histogram(values={"DONE": 5}),
        task_categories=Histogram(values={}),
        task_days=Histogram(values={"Monday": 5}),
        tags={

            "python": Tag(

                name="python",

                frequency=Frequency(total=5),

                relations=Relations(name="python", relations={}),

                time_range=TimeRange(),

                total_tasks=5,

                avg_tasks_per_day=0.0,

                max_single_day_count=0,

            )

        },
        timerange=TimeRange(earliest=None, latest=None, timeline={}),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_groups=tag_groups,
    )

    args = argparse.Namespace(
        show="tags",
        max_results=10,
        max_tags=5,
        max_relations=3,
        min_group_size=3,
        max_groups=5,
        buckets=50,
    )

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_results(result, [], args, (set(), None, None, ["DONE"], ["TODO"]))

        output = sys.stdout.getvalue()

        assert "Tag groups:" in output
        assert "java, programming, coding" in output
        assert "python, programming" not in output

    finally:
        sys.stdout = original_stdout


def test_display_results_tag_groups_with_excluded_tags() -> None:
    """Test display_results filters excluded tags from groups."""
    from io import StringIO

    from orgstats.analyze import (
        AnalysisResult,
        Frequency,
        Group,
        TimeRange,
    )
    from orgstats.cli import display_results
    from orgstats.histogram import Histogram

    tag_groups = [
        Group(tags=["python", "test", "programming"], time_range=TimeRange()),
        Group(tags=["java", "test"], time_range=TimeRange()),
    ]

    result = AnalysisResult(
        total_tasks=5,
        task_states=Histogram(values={"DONE": 5}),
        task_categories=Histogram(values={}),
        task_days=Histogram(values={"Monday": 5}),
        tags={

            "python": Tag(

                name="python",

                frequency=Frequency(total=5),

                relations=Relations(name="python", relations={}),

                time_range=TimeRange(),

                total_tasks=5,

                avg_tasks_per_day=0.0,

                max_single_day_count=0,

            )

        },
        timerange=TimeRange(earliest=None, latest=None, timeline={}),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_groups=tag_groups,
    )

    args = argparse.Namespace(
        show="tags",
        max_results=10,
        max_tags=5,
        max_relations=3,
        min_group_size=2,
        max_groups=5,
        buckets=50,
    )

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_results(result, [], args, ({"test"}, None, None, ["DONE"], ["TODO"]))

        output = sys.stdout.getvalue()

        assert "Tag groups:" in output
        assert "python, programming" in output
        assert "java" not in output

    finally:
        sys.stdout = original_stdout


def test_display_results_no_tag_groups() -> None:
    """Test display_results works when tag_groups is empty."""
    from io import StringIO

    from orgstats.analyze import (
        AnalysisResult,
        Frequency,
        TimeRange,
    )
    from orgstats.cli import display_results
    from orgstats.histogram import Histogram

    result = AnalysisResult(
        total_tasks=5,
        task_states=Histogram(values={"DONE": 5}),
        task_categories=Histogram(values={}),
        task_days=Histogram(values={"Monday": 5}),
        tags={

            "python": Tag(

                name="python",

                frequency=Frequency(total=5),

                relations=Relations(name="python", relations={}),

                time_range=TimeRange(),

                total_tasks=5,

                avg_tasks_per_day=0.0,

                max_single_day_count=0,

            )

        },
        timerange=TimeRange(earliest=None, latest=None, timeline={}),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tag_groups=[],
    )

    args = argparse.Namespace(
        show="tags",
        max_results=10,
        max_tags=5,
        max_relations=3,
        min_group_size=3,
        max_groups=5,
        buckets=50,
    )

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_results(result, [], args, (set(), None, None, ["DONE"], ["TODO"]))

        output = sys.stdout.getvalue()

        assert "Tag groups:" in output

    finally:
        sys.stdout = original_stdout


def test_main_no_results_after_filtering() -> None:
    """Test that main prints 'No results' when all nodes filtered out."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--filter-gamify-exp-above",
            "1000",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout
    assert "Total tasks:" not in result.stdout


def test_main_no_results_with_impossible_filter() -> None:
    """Test 'No results' with filter that excludes everything."""
    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orgstats",
            "--filter-gamify-exp-above",
            "1000",
            "--filter-gamify-exp-below",
            "1",
            fixture_path,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "No results" in result.stdout


def test_main_with_tag_groups() -> None:
    """Test main displays tag groups when present."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--min-group-size", "2", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" in result.stdout


def test_main_with_tag_groups_high_min_size() -> None:
    """Test main with min_group_size that filters out all groups."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")

    result = subprocess.run(
        [sys.executable, "-m", "orgstats", "--min-group-size", "100", fixture_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Tag groups:" in result.stdout


def test_filter_nodes_deprecated() -> None:
    """Test deprecated filter_nodes function still works."""
    from orgstats.cli import filter_nodes, load_nodes

    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")
    nodes, _, _ = load_nodes([fixture_path], ["TODO"], ["DONE"], [])

    filtered = filter_nodes(nodes, "simple")

    assert len(filtered) <= len(nodes)


def test_filter_nodes_all() -> None:
    """Test filter_nodes with 'all' returns all nodes."""
    from orgstats.cli import filter_nodes, load_nodes

    fixture_path = os.path.join(FIXTURES_DIR, "gamify_exp_test.org")
    nodes, _, _ = load_nodes([fixture_path], ["TODO"], ["DONE"], [])

    filtered = filter_nodes(nodes, "all")

    assert len(filtered) == len(nodes)


def test_parse_filter_order_from_argv() -> None:
    """Test parse_filter_order_from_argv extracts filter args."""
    from orgstats.cli import parse_filter_order_from_argv

    argv = [
        "orgstats",
        "--filter",
        "simple",
        "--filter-gamify-exp-above",
        "10",
        "file.org",
    ]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter", "--filter-gamify-exp-above"]


def test_parse_filter_order_from_argv_no_filters() -> None:
    """Test parse_filter_order_from_argv with no filter args."""
    from orgstats.cli import parse_filter_order_from_argv

    argv = ["orgstats", "--max-results", "10", "file.org"]

    result = parse_filter_order_from_argv(argv)

    assert result == []


def test_parse_filter_order_from_argv_multiple_properties() -> None:
    """Test parse_filter_order_from_argv with multiple property filters."""
    from orgstats.cli import parse_filter_order_from_argv

    argv = [
        "orgstats",
        "--filter-property",
        "key1=val1",
        "--filter-property",
        "key2=val2",
        "file.org",
    ]

    result = parse_filter_order_from_argv(argv)

    assert result == ["--filter-property", "--filter-property"]


def test_main_entry_point() -> None:
    """Test that __main__ entry point calls main()."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from orgstats.cli import main; import sys; sys.argv = ['cli', '{fixture_path}']; main()",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Total tasks:" in result.stdout


def test_display_groups_with_max_groups_zero() -> None:
    """Test display_groups with max_groups=0 omits section entirely."""
    from orgstats.analyze import Group, TimeRange
    from orgstats.cli import display_groups

    groups = [Group(tags=["python", "test"], time_range=TimeRange())]
    exclude_set: set[str] = set()

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_groups(groups, exclude_set, (2, 50, None, None, TimeRange()), 0)

        output = sys.stdout.getvalue()

        assert output == ""
        assert "Tag groups:" not in output

    finally:
        sys.stdout = original_stdout


def test_display_groups_with_max_groups_limit() -> None:
    """Test display_groups respects max_groups limit."""
    from orgstats.analyze import Group, TimeRange
    from orgstats.cli import display_groups

    groups = [
        Group(tags=["a", "b", "c"], time_range=TimeRange()),
        Group(tags=["d", "e"], time_range=TimeRange()),
        Group(tags=["f", "g"], time_range=TimeRange()),
    ]
    exclude_set: set[str] = set()

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_groups(groups, exclude_set, (2, 50, None, None, TimeRange()), 2)

        output = sys.stdout.getvalue()

        assert "Tag groups:" in output
        assert "a, b, c" in output
        assert "d, e" in output
        assert "f, g" not in output

    finally:
        sys.stdout = original_stdout


def test_display_groups_shows_empty_section() -> None:
    """Test display_groups shows section heading with no groups when max_groups > 0."""
    from orgstats.analyze import Group, TimeRange
    from orgstats.cli import display_groups

    groups = [Group(tags=["a", "b"], time_range=TimeRange())]
    exclude_set: set[str] = set()

    original_stdout = sys.stdout
    try:
        sys.stdout = StringIO()

        display_groups(groups, exclude_set, (100, 50, None, None, TimeRange()), 5)

        output = sys.stdout.getvalue()

        assert "Tag groups:" in output
        assert "a, b" not in output

    finally:
        sys.stdout = original_stdout
