"""Terminal output formatting for the org CLI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

import orgparse
from colorama import Style

from org.analyze import AnalysisResult, Group, Tag, TimeRange, clean
from org.cli_common import get_top_tasks
from org.color import bright_white, dim_white, get_state_color, magenta
from org.histogram import Histogram, RenderConfig, render_histogram
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


def _lines_to_text(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _apply_indent(lines: list[str], indent: str) -> list[str]:
    if not indent:
        return lines
    return [f"{indent}{line}" if line else "" for line in lines]


def _section_header_lines(title: str, color_enabled: bool) -> list[str]:
    return ["", bright_white(title, color_enabled)]


@dataclass(frozen=True)
class TimelineFormatConfig:
    """Configuration for rendering timeline charts."""

    num_buckets: int
    color_enabled: bool
    indent: str


@dataclass(frozen=True)
class TagBlockConfig:
    """Configuration for rendering a tag block."""

    max_relations: int
    exclude_set: set[str]
    date_from: datetime | None
    date_until: datetime | None
    global_timerange: TimeRange
    timeline: TimelineFormatConfig
    name_indent: str
    stats_indent: str


@dataclass(frozen=True)
class GroupBlockConfig:
    """Configuration for rendering a group block."""

    date_from: datetime | None
    date_until: datetime | None
    global_timerange: TimeRange
    timeline: TimelineFormatConfig
    name_indent: str
    stats_indent: str


@dataclass(frozen=True)
class HistogramSectionConfig:
    """Configuration for rendering histogram sections."""

    buckets: int
    order: list[str]
    render_config: RenderConfig
    indent: str


@dataclass(frozen=True)
class TopTasksSectionConfig:
    """Configuration for rendering the top tasks section."""

    max_results: int
    color_enabled: bool
    done_keys: list[str]
    todo_keys: list[str]
    indent: str


def _format_timeline_lines(
    timeline: dict[date, int],
    earliest_date: date,
    latest_date: date,
    config: TimelineFormatConfig,
) -> list[str]:
    date_line, chart_line, underline = render_timeline_chart(
        timeline,
        earliest_date,
        latest_date,
        config.num_buckets,
        config.color_enabled,
    )
    return _apply_indent([date_line, chart_line, underline], config.indent)


def _format_tag_block(name: str, tag: Tag, config: TagBlockConfig) -> list[str]:
    lines: list[str] = []
    time_range = tag.time_range
    if time_range and time_range.earliest and time_range.timeline:
        earliest_date = select_earliest_date(config.date_from, config.global_timerange, time_range)
        latest_date = select_latest_date(config.date_until, config.global_timerange, time_range)
        if earliest_date and latest_date:
            lines.extend(
                _format_timeline_lines(
                    time_range.timeline,
                    earliest_date,
                    latest_date,
                    config.timeline,
                )
            )

    lines.append(f"{config.name_indent}{name}")
    total_tasks_value = magenta(str(tag.total_tasks), config.timeline.color_enabled)
    lines.append(f"{config.stats_indent}Total tasks: {total_tasks_value}")
    if tag.time_range.earliest and tag.time_range.latest:
        avg_value = magenta(f"{tag.avg_tasks_per_day:.2f}", config.timeline.color_enabled)
        max_value = magenta(str(tag.max_single_day_count), config.timeline.color_enabled)
        lines.append(f"{config.stats_indent}Average tasks per day: {avg_value}")
        lines.append(f"{config.stats_indent}Max tasks on a single day: {max_value}")

    if config.max_relations > 0 and tag.relations:
        exclude_lower = {value.lower() for value in config.exclude_set}
        filtered_relations = {
            rel_name: count
            for rel_name, count in tag.relations.items()
            if rel_name.lower() not in exclude_lower
        }
        sorted_relations = sorted(filtered_relations.items(), key=lambda x: x[1], reverse=True)[
            0 : config.max_relations
        ]
        if sorted_relations:
            relation_indent = f"{config.stats_indent}  "
            lines.append(f"{config.stats_indent}Top relations:")
            lines.extend(
                [
                    f"{relation_indent}{related_name} ({count})"
                    for related_name, count in sorted_relations
                ]
            )
    return lines


def _format_group_block(
    group_tags: list[str],
    group: Group,
    config: GroupBlockConfig,
) -> list[str]:
    lines: list[str] = []
    earliest_date = select_earliest_date(
        config.date_from, config.global_timerange, group.time_range
    )
    latest_date = select_latest_date(config.date_until, config.global_timerange, group.time_range)
    if earliest_date and latest_date:
        lines.extend(
            _format_timeline_lines(
                group.time_range.timeline,
                earliest_date,
                latest_date,
                config.timeline,
            )
        )

    lines.append(f"{config.name_indent}{', '.join(group_tags)}")
    total_tasks_value = magenta(str(group.total_tasks), config.timeline.color_enabled)
    avg_value = magenta(f"{group.avg_tasks_per_day:.2f}", config.timeline.color_enabled)
    max_value = magenta(str(group.max_single_day_count), config.timeline.color_enabled)
    lines.append(f"{config.stats_indent}Total tasks: {total_tasks_value}")
    lines.append(f"{config.stats_indent}Average tasks per day: {avg_value}")
    lines.append(f"{config.stats_indent}Max tasks on a single day: {max_value}")
    return lines


def format_category_section(
    category_name: str,
    tags: dict[str, Tag],
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, int, set[str], bool],
    order_fn: Callable[[tuple[str, Tag]], int],
    indent: str = "",
) -> str:
    """Return formatted output for a single category section."""
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
        return ""

    cleaned = clean(exclude_set, tags)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0:max_items]

    lines = _section_header_lines(category_name.upper(), color_enabled)

    if not sorted_items:
        lines.append("  No results")
        return _lines_to_text(_apply_indent(lines, indent))

    for idx, (name, tag) in enumerate(sorted_items):
        if idx > 0:
            lines.append("")
        lines.extend(
            _format_tag_block(
                name,
                tag,
                TagBlockConfig(
                    max_relations=max_relations,
                    exclude_set=exclude_set,
                    date_from=date_from,
                    date_until=date_until,
                    global_timerange=global_timerange,
                    timeline=TimelineFormatConfig(
                        num_buckets=num_buckets,
                        color_enabled=color_enabled,
                        indent="  ",
                    ),
                    name_indent="  ",
                    stats_indent="    ",
                ),
            )
        )

    return _lines_to_text(_apply_indent(lines, indent))


def format_selected_items(
    tags: dict[str, Tag],
    show: list[str] | None,
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, set[str], bool],
    indent: str = "",
) -> str:
    """Return formatted output for selected tags without a section header."""
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
        return _lines_to_text(_apply_indent(["No results"], indent))

    lines: list[str] = []
    for idx, (name, tag) in enumerate(selected_items):
        if idx > 0:
            lines.append("")
        lines.extend(
            _format_tag_block(
                name,
                tag,
                TagBlockConfig(
                    max_relations=max_relations,
                    exclude_set=exclude_set,
                    date_from=date_from,
                    date_until=date_until,
                    global_timerange=global_timerange,
                    timeline=TimelineFormatConfig(
                        num_buckets=num_buckets,
                        color_enabled=color_enabled,
                        indent="",
                    ),
                    name_indent="",
                    stats_indent="  ",
                ),
            )
        )

    return _lines_to_text(_apply_indent(lines, indent))


def format_groups_section(
    groups: list[Group],
    exclude_set: set[str],
    config: tuple[int, int, datetime | None, datetime | None, TimeRange, bool],
    max_groups: int,
    indent: str = "",
) -> str:
    """Return formatted output for tag groups section."""
    if max_groups == 0:
        return ""

    min_group_size, num_buckets, date_from, date_until, global_timerange, color_enabled = config

    filtered_groups = []
    for group in groups:
        filtered_tags = [tag for tag in group.tags if tag not in exclude_set]
        if len(filtered_tags) >= min_group_size:
            filtered_groups.append((filtered_tags, group))

    filtered_groups.sort(key=lambda x: len(x[0]), reverse=True)
    filtered_groups = filtered_groups[:max_groups]

    lines = _section_header_lines("GROUPS", color_enabled)

    if not filtered_groups:
        lines.append("  No results")
        return _lines_to_text(_apply_indent(lines, indent))

    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            lines.append("")
        lines.extend(
            _format_group_block(
                group_tags,
                group,
                GroupBlockConfig(
                    date_from=date_from,
                    date_until=date_until,
                    global_timerange=global_timerange,
                    timeline=TimelineFormatConfig(
                        num_buckets=num_buckets,
                        color_enabled=color_enabled,
                        indent="  ",
                    ),
                    name_indent="  ",
                    stats_indent="    ",
                ),
            )
        )

    return _lines_to_text(_apply_indent(lines, indent))


def format_group_list(
    groups: list[Group],
    config: tuple[int, int, datetime | None, datetime | None, TimeRange, set[str], bool],
    indent: str = "",
) -> str:
    """Return formatted output for group stats without a section header."""
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
        return _lines_to_text(_apply_indent(["No results"], indent))

    lines: list[str] = []
    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            lines.append("")
        lines.extend(
            _format_group_block(
                group_tags,
                group,
                GroupBlockConfig(
                    date_from=date_from,
                    date_until=date_until,
                    global_timerange=global_timerange,
                    timeline=TimelineFormatConfig(
                        num_buckets=num_buckets,
                        color_enabled=color_enabled,
                        indent="",
                    ),
                    name_indent="",
                    stats_indent="  ",
                ),
            )
        )

    return _lines_to_text(_apply_indent(lines, indent))


def format_top_tasks_section(
    nodes: list[orgparse.node.OrgNode],
    config: TopTasksSectionConfig,
) -> str:
    """Return formatted output for the top tasks section."""
    top_tasks = get_top_tasks(nodes, config.max_results)
    if not top_tasks:
        return ""

    lines = _section_header_lines("TASKS", config.color_enabled)
    for node in top_tasks:
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        colored_filename = dim_white(f"{filename}:", config.color_enabled)
        todo_state = node.todo if node.todo else ""
        heading = node.heading if node.heading else ""

        if todo_state:
            state_color = get_state_color(
                todo_state,
                config.done_keys,
                config.todo_keys,
                config.color_enabled,
            )
            if config.color_enabled and state_color:
                colored_state = f"{state_color}{todo_state}{Style.RESET_ALL}"
            else:
                colored_state = todo_state
            lines.append(f"  {colored_filename} {colored_state} {heading}".strip())
        else:
            lines.append(f"  {colored_filename} {heading}".strip())

    return _lines_to_text(_apply_indent(lines, config.indent))


def _format_histogram_section(
    title: str,
    histogram: Histogram,
    config: HistogramSectionConfig,
) -> list[str]:
    lines = _section_header_lines(title, config.render_config.color_enabled)
    histogram_lines = render_histogram(
        histogram,
        config.buckets,
        config.order,
        config.render_config,
    )
    lines.extend([f"  {line}" for line in histogram_lines])
    return _apply_indent(lines, config.indent)


def format_task_summary(
    result: AnalysisResult,
    args: TaskDisplayArgs,
    display_config: tuple[datetime | None, datetime | None, list[str], list[str], bool],
    indent: str = "",
) -> str:
    """Return formatted global task statistics without tag/group sections."""
    date_from, date_until, done_keys, todo_keys, color_enabled = display_config

    lines: list[str] = []
    if result.timerange.earliest and result.timerange.latest and result.timerange.timeline:
        earliest_date = date_from.date() if date_from else result.timerange.earliest.date()
        latest_date = date_until.date() if date_until else result.timerange.latest.date()
        lines.append("")
        lines.extend(
            _format_timeline_lines(
                result.timerange.timeline,
                earliest_date,
                latest_date,
                TimelineFormatConfig(
                    num_buckets=args.buckets,
                    color_enabled=color_enabled,
                    indent="",
                ),
            )
        )

    total_tasks_value = magenta(str(result.total_tasks), color_enabled)
    lines.append(f"Total tasks: {total_tasks_value}")

    if result.timerange.earliest and result.timerange.latest:
        avg_value = magenta(f"{result.avg_tasks_per_day:.2f}", color_enabled)
        max_single_value = magenta(str(result.max_single_day_count), color_enabled)
        max_repeat_value = magenta(str(result.max_repeat_count), color_enabled)
        lines.append(f"Average tasks per day: {avg_value}")
        lines.append(f"Max tasks on a single day: {max_single_value}")
        lines.append(f"Max repeats of a single task: {max_repeat_value}")

    remaining_states = sorted(
        set(result.task_states.values.keys()) - set(done_keys) - set(todo_keys)
    )
    state_order = done_keys + todo_keys + remaining_states
    lines.extend(
        _format_histogram_section(
            "Task states:",
            result.task_states,
            HistogramSectionConfig(
                buckets=args.buckets,
                order=state_order,
                render_config=RenderConfig(
                    color_enabled=color_enabled,
                    histogram_type="task_states",
                    done_keys=done_keys,
                    todo_keys=todo_keys,
                ),
                indent="",
            ),
        )
    )

    category_order = sorted(result.task_categories.values.keys())
    lines.extend(
        _format_histogram_section(
            "Task categories:",
            result.task_categories,
            HistogramSectionConfig(
                buckets=args.buckets,
                order=category_order,
                render_config=RenderConfig(color_enabled=color_enabled),
                indent="",
            ),
        )
    )

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
    lines.extend(
        _format_histogram_section(
            "Task occurrence by day of week:",
            result.task_days,
            HistogramSectionConfig(
                buckets=args.buckets,
                order=day_order,
                render_config=RenderConfig(color_enabled=color_enabled),
                indent="",
            ),
        )
    )

    return _lines_to_text(_apply_indent(lines, indent))


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
