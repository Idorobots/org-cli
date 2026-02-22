"""Terminal output generation for the org CLI."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

import orgparse
from colorama import Style

from org.analyze import AnalysisResult, Group, Tag, TimeRange, clean
from org.cli_common import CATEGORY_NAMES, get_top_tasks
from org.color import bright_white, dim_white, get_state_color, magenta
from org.histogram import RenderConfig, render_histogram
from org.plot import render_timeline_chart


def select_earliest_date(
    date_from: datetime | None,
    global_timerange: TimeRange,
    local_timerange: TimeRange,
) -> date | None:
    """Select earliest date using priority: user filter > global > local.

    Args:
        date_from: User-provided filter date or None
        global_timerange: Global timerange across all tasks
        local_timerange: Local timerange for specific item

    Returns:
        Selected earliest date or None if no dates available
    """
    if date_from:
        return date_from.date()
    if global_timerange.earliest:
        return global_timerange.earliest.date()
    if local_timerange.earliest:
        return local_timerange.earliest.date()
    return None


def select_latest_date(
    date_until: datetime | None,
    global_timerange: TimeRange,
    local_timerange: TimeRange,
) -> date | None:
    """Select latest date using priority: user filter > global > local.

    Args:
        date_until: User-provided filter date or None
        global_timerange: Global timerange across all tasks
        local_timerange: Local timerange for specific item

    Returns:
        Selected latest date or None if no dates available
    """
    if date_until:
        return date_until.date()
    if global_timerange.latest:
        return global_timerange.latest.date()
    if local_timerange.latest:
        return local_timerange.latest.date()
    if local_timerange.earliest:
        return local_timerange.earliest.date()
    return None


def display_category(
    category_name: str,
    tags: dict[str, Tag],
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, int, set[str], bool],
    order_fn: Callable[[tuple[str, Tag]], int],
) -> None:
    """Display formatted output for a single category.

    Args:
        category_name: Display name for the category (e.g., "tags", "heading words")
        tags: Dictionary mapping tag names to Tag objects
        config: Tuple of (max_results, max_relations, num_buckets, date_from, date_until,
                         global_timerange, max_items, exclude_set, color_enabled)
        order_fn: Function to sort items by
    """
    (
        _max_results,
        max_relations,
        num_buckets,
        date_from,
        date_until,
        global_timerange,
        max_items,
        exclude_set,
        color_enabled,
    ) = config

    if max_items == 0:
        return
    cleaned = clean(exclude_set, tags)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0:max_items]

    section_header = bright_white(f"\n{category_name.upper()}", color_enabled)
    print(section_header)

    if not sorted_items:
        print("  No results")
        return
    for idx, (name, tag) in enumerate(sorted_items):
        if idx > 0:
            print()

        time_range = tag.time_range

        if time_range and time_range.earliest and time_range.timeline:
            earliest_date = select_earliest_date(date_from, global_timerange, time_range)
            latest_date = select_latest_date(date_until, global_timerange, time_range)

            if earliest_date and latest_date:
                date_line, chart_line, underline = render_timeline_chart(
                    time_range.timeline,
                    earliest_date,
                    latest_date,
                    num_buckets,
                    color_enabled,
                )
                print(f"  {date_line}")
                print(f"  {chart_line}")
                print(f"  {underline}")

        print(f"  {name}")
        total_tasks_value = magenta(str(tag.total_tasks), color_enabled)
        print(f"    Total tasks: {total_tasks_value}")
        if tag.time_range.earliest and tag.time_range.latest:
            avg_value = magenta(f"{tag.avg_tasks_per_day:.2f}", color_enabled)
            max_value = magenta(str(tag.max_single_day_count), color_enabled)
            print(f"    Average tasks per day: {avg_value}")
            print(f"    Max tasks on a single day: {max_value}")

        if max_relations > 0 and tag.relations:
            filtered_relations = {
                rel_name: count
                for rel_name, count in tag.relations.items()
                if rel_name.lower() not in {e.lower() for e in exclude_set}
            }
            sorted_relations = sorted(filtered_relations.items(), key=lambda x: x[1], reverse=True)[
                0:max_relations
            ]

            if sorted_relations:
                print("    Top relations:")
                for related_name, count in sorted_relations:
                    print(f"      {related_name} ({count})")


def display_selected_items(
    tags: dict[str, Tag],
    show: list[str] | None,
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, set[str], bool],
) -> None:
    """Display formatted output for a selected tag list without leading indent."""
    (
        max_results,
        max_relations,
        num_buckets,
        date_from,
        date_until,
        global_timerange,
        exclude_set,
        color_enabled,
    ) = config

    cleaned = clean(exclude_set, tags)

    if show is not None:
        selected_items = [(name, cleaned[name]) for name in show if name in cleaned]
        selected_items = selected_items[:max_results]
    else:
        selected_items = sorted(cleaned.items(), key=lambda item: -item[1].total_tasks)[
            0:max_results
        ]

    if not selected_items:
        print("No results")
        return

    for idx, (name, tag) in enumerate(selected_items):
        if idx > 0:
            print()

        time_range = tag.time_range

        if time_range and time_range.earliest and time_range.timeline:
            earliest_date = select_earliest_date(date_from, global_timerange, time_range)
            latest_date = select_latest_date(date_until, global_timerange, time_range)

            if earliest_date and latest_date:
                date_line, chart_line, underline = render_timeline_chart(
                    time_range.timeline,
                    earliest_date,
                    latest_date,
                    num_buckets,
                    color_enabled,
                )
                print(date_line)
                print(chart_line)
                print(underline)

        print(name)
        total_tasks_value = magenta(str(tag.total_tasks), color_enabled)
        print(f"  Total tasks: {total_tasks_value}")
        if tag.time_range.earliest and tag.time_range.latest:
            avg_value = magenta(f"{tag.avg_tasks_per_day:.2f}", color_enabled)
            max_value = magenta(str(tag.max_single_day_count), color_enabled)
            print(f"  Average tasks per day: {avg_value}")
            print(f"  Max tasks on a single day: {max_value}")

        if max_relations > 0 and tag.relations:
            filtered_relations = {
                rel_name: count
                for rel_name, count in tag.relations.items()
                if rel_name.lower() not in {e.lower() for e in exclude_set}
            }
            sorted_relations = sorted(filtered_relations.items(), key=lambda x: x[1], reverse=True)[
                0:max_relations
            ]

            if sorted_relations:
                print("  Top relations:")
                for related_name, count in sorted_relations:
                    print(f"    {related_name} ({count})")


def display_groups(
    groups: list[Group],
    exclude_set: set[str],
    config: tuple[int, int, datetime | None, datetime | None, TimeRange, bool],
    max_groups: int,
) -> None:
    """Display tag groups with timelines.

    Args:
        groups: List of Group objects
        exclude_set: Set of tags to exclude
        config: Tuple of (min_group_size, num_buckets, date_from, date_until,
                         global_timerange, color_enabled)
        max_groups: Maximum number of groups to display (0 to omit section entirely)
    """
    if max_groups == 0:
        return

    min_group_size, num_buckets, date_from, date_until, global_timerange, color_enabled = config

    filtered_groups = []
    for group in groups:
        filtered_tags = [tag for tag in group.tags if tag not in exclude_set]
        if len(filtered_tags) >= min_group_size:
            filtered_groups.append((filtered_tags, group))

    filtered_groups.sort(key=lambda x: len(x[0]), reverse=True)
    filtered_groups = filtered_groups[:max_groups]

    section_header = bright_white("\nGROUPS", color_enabled)
    print(section_header)

    if not filtered_groups:
        print("  No results")
        return
    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            print()

        earliest_date = select_earliest_date(date_from, global_timerange, group.time_range)
        latest_date = select_latest_date(date_until, global_timerange, group.time_range)

        if earliest_date and latest_date:
            date_line, chart_line, underline = render_timeline_chart(
                group.time_range.timeline,
                earliest_date,
                latest_date,
                num_buckets,
                color_enabled,
            )
            print(f"  {date_line}")
            print(f"  {chart_line}")
            print(f"  {underline}")

        print(f"  {', '.join(group_tags)}")
        total_tasks_value = magenta(str(group.total_tasks), color_enabled)
        avg_value = magenta(f"{group.avg_tasks_per_day:.2f}", color_enabled)
        max_value = magenta(str(group.max_single_day_count), color_enabled)
        print(f"    Total tasks: {total_tasks_value}")
        print(f"    Average tasks per day: {avg_value}")
        print(f"    Max tasks on a single day: {max_value}")


def display_group_list(
    groups: list[Group],
    config: tuple[int, int, datetime | None, datetime | None, TimeRange, set[str], bool],
) -> None:
    """Display group stats without the leading indent."""
    (
        max_results,
        num_buckets,
        date_from,
        date_until,
        global_timerange,
        exclude_set,
        color_enabled,
    ) = config

    exclude_lower = {value.lower() for value in exclude_set}
    filtered_groups = []
    for group in groups:
        display_tags = [tag for tag in group.tags if tag.lower() not in exclude_lower]
        if display_tags:
            filtered_groups.append((display_tags, group))

    filtered_groups = filtered_groups[:max_results]

    if not filtered_groups:
        print("No results")
        return

    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            print()

        earliest_date = select_earliest_date(date_from, global_timerange, group.time_range)
        latest_date = select_latest_date(date_until, global_timerange, group.time_range)

        if earliest_date and latest_date:
            date_line, chart_line, underline = render_timeline_chart(
                group.time_range.timeline,
                earliest_date,
                latest_date,
                num_buckets,
                color_enabled,
            )
            print(date_line)
            print(chart_line)
            print(underline)

        print(f"{', '.join(group_tags)}")
        total_tasks_value = magenta(str(group.total_tasks), color_enabled)
        avg_value = magenta(f"{group.avg_tasks_per_day:.2f}", color_enabled)
        max_value = magenta(str(group.max_single_day_count), color_enabled)
        print(f"  Total tasks: {total_tasks_value}")
        print(f"  Average tasks per day: {avg_value}")
        print(f"  Max tasks on a single day: {max_value}")


def display_top_tasks(
    nodes: list[orgparse.node.OrgNode],
    max_results: int,
    color_enabled: bool,
    done_keys: list[str],
    todo_keys: list[str],
) -> None:
    """Display top tasks sorted by most recent timestamp.

    Args:
        nodes: List of org-mode nodes
        max_results: Maximum number of results to display
        color_enabled: Whether to apply colors to the output
        done_keys: List of done state keywords
        todo_keys: List of todo state keywords
    """
    top_tasks = get_top_tasks(nodes, max_results)

    if not top_tasks:
        return

    section_header = bright_white("\nTASKS", color_enabled)
    print(section_header)
    for node in top_tasks:
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        colored_filename = dim_white(f"{filename}:", color_enabled)
        todo_state = node.todo if node.todo else ""
        heading = node.heading if node.heading else ""

        if todo_state:
            state_color = get_state_color(todo_state, done_keys, todo_keys, color_enabled)
            if color_enabled and state_color:
                colored_state = f"{state_color}{todo_state}{Style.RESET_ALL}"
            else:
                colored_state = todo_state
            print(f"  {colored_filename} {colored_state} {heading}".strip())
        else:
            print(f"  {colored_filename} {heading}".strip())


def display_results(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: SummaryDisplayArgs,
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str], bool],
) -> None:
    """Display analysis results in formatted output.

    Args:
        result: Analysis results to display
        nodes: Filtered org-mode nodes used for analysis
        args: Command-line arguments containing display configuration
        display_config: Tuple of (exclude_set, date_from, date_until, done_keys, todo_keys,
                                  color_enabled)
    """
    exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled = display_config
    if result.timerange.earliest and result.timerange.latest and result.timerange.timeline:
        earliest_date = date_from.date() if date_from else result.timerange.earliest.date()
        latest_date = date_until.date() if date_until else result.timerange.latest.date()
        date_line, chart_line, underline = render_timeline_chart(
            result.timerange.timeline,
            earliest_date,
            latest_date,
            args.buckets,
            color_enabled,
        )
        print()
        print(date_line)
        print(chart_line)
        print(underline)

    total_tasks_value = magenta(str(result.total_tasks), color_enabled)
    print(f"Total tasks: {total_tasks_value}")

    if result.timerange.earliest and result.timerange.latest:
        avg_value = magenta(f"{result.avg_tasks_per_day:.2f}", color_enabled)
        max_single_value = magenta(str(result.max_single_day_count), color_enabled)
        max_repeat_value = magenta(str(result.max_repeat_count), color_enabled)
        print(f"Average tasks per day: {avg_value}")
        print(f"Max tasks on a single day: {max_single_value}")
        print(f"Max repeats of a single task: {max_repeat_value}")

    task_states_header = bright_white("\nTask states:", color_enabled)
    print(task_states_header)
    remaining_states = sorted(
        set(result.task_states.values.keys()) - set(done_keys) - set(todo_keys)
    )
    state_order = done_keys + todo_keys + remaining_states
    histogram_lines = render_histogram(
        result.task_states,
        args.buckets,
        state_order,
        RenderConfig(
            color_enabled=color_enabled,
            histogram_type="task_states",
            done_keys=done_keys,
            todo_keys=todo_keys,
        ),
    )
    for line in histogram_lines:
        print(f"  {line}")

    task_categories_header = bright_white("\nTask categories:", color_enabled)
    print(task_categories_header)
    category_order = sorted(result.task_categories.values.keys())
    histogram_lines = render_histogram(
        result.task_categories,
        args.buckets,
        category_order,
        RenderConfig(color_enabled=color_enabled),
    )
    for line in histogram_lines:
        print(f"  {line}")

    task_days_header = bright_white("\nTask occurrence by day of week:", color_enabled)
    print(task_days_header)
    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "unknown",
    ]
    histogram_lines = render_histogram(
        result.task_days, args.buckets, day_order, RenderConfig(color_enabled=color_enabled)
    )
    for line in histogram_lines:
        print(f"  {line}")

    display_top_tasks(nodes, args.max_results, color_enabled, done_keys, todo_keys)

    category_name = CATEGORY_NAMES[args.use]

    def order_by_total(item: tuple[str, Tag]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total_tasks

    display_category(
        category_name,
        result.tags,
        (
            args.max_results,
            args.max_relations,
            args.buckets,
            date_from,
            date_until,
            result.timerange,
            args.max_tags,
            exclude_set,
            color_enabled,
        ),
        order_by_total,
    )

    display_groups(
        result.tag_groups,
        exclude_set,
        (args.min_group_size, args.buckets, date_from, date_until, result.timerange, color_enabled),
        args.max_groups,
    )


def display_task_summary(
    result: AnalysisResult,
    args: TaskDisplayArgs,
    display_config: tuple[datetime | None, datetime | None, list[str], list[str], bool],
) -> None:
    """Display global task statistics without tag/group sections.

    Args:
        result: Analysis results to display
        args: Command-line arguments containing display configuration
        display_config: Tuple of (date_from, date_until, done_keys, todo_keys, color_enabled)
    """
    date_from, date_until, done_keys, todo_keys, color_enabled = display_config

    if result.timerange.earliest and result.timerange.latest and result.timerange.timeline:
        earliest_date = date_from.date() if date_from else result.timerange.earliest.date()
        latest_date = date_until.date() if date_until else result.timerange.latest.date()
        date_line, chart_line, underline = render_timeline_chart(
            result.timerange.timeline,
            earliest_date,
            latest_date,
            args.buckets,
            color_enabled,
        )
        print()
        print(date_line)
        print(chart_line)
        print(underline)

    total_tasks_value = magenta(str(result.total_tasks), color_enabled)
    print(f"Total tasks: {total_tasks_value}")

    if result.timerange.earliest and result.timerange.latest:
        avg_value = magenta(f"{result.avg_tasks_per_day:.2f}", color_enabled)
        max_single_value = magenta(str(result.max_single_day_count), color_enabled)
        max_repeat_value = magenta(str(result.max_repeat_count), color_enabled)
        print(f"Average tasks per day: {avg_value}")
        print(f"Max tasks on a single day: {max_single_value}")
        print(f"Max repeats of a single task: {max_repeat_value}")

    task_states_header = bright_white("\nTask states:", color_enabled)
    print(task_states_header)
    remaining_states = sorted(
        set(result.task_states.values.keys()) - set(done_keys) - set(todo_keys)
    )
    state_order = done_keys + todo_keys + remaining_states
    histogram_lines = render_histogram(
        result.task_states,
        args.buckets,
        state_order,
        RenderConfig(
            color_enabled=color_enabled,
            histogram_type="task_states",
            done_keys=done_keys,
            todo_keys=todo_keys,
        ),
    )
    for line in histogram_lines:
        print(f"  {line}")

    task_categories_header = bright_white("\nTask categories:", color_enabled)
    print(task_categories_header)
    category_order = sorted(result.task_categories.values.keys())
    histogram_lines = render_histogram(
        result.task_categories,
        args.buckets,
        category_order,
        RenderConfig(color_enabled=color_enabled),
    )
    for line in histogram_lines:
        print(f"  {line}")

    task_days_header = bright_white("\nTask occurrence by day of week:", color_enabled)
    print(task_days_header)
    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "unknown",
    ]
    histogram_lines = render_histogram(
        result.task_days, args.buckets, day_order, RenderConfig(color_enabled=color_enabled)
    )
    for line in histogram_lines:
        print(f"  {line}")


class SummaryDisplayArgs(Protocol):
    """Protocol for display arguments used in summary output."""

    buckets: int
    max_results: int
    max_relations: int
    max_tags: int
    min_group_size: int
    max_groups: int
    use: str


class TaskDisplayArgs(Protocol):
    """Protocol for display arguments used in task summary output."""

    buckets: int
