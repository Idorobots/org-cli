"""Terminal output formatting for the org CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import orgparse
from colorama import Style
from colorama import init as colorama_init

from org.analyze import Group, Tag, TimeRange
from org.cli_common import get_top_tasks
from org.color import bright_white, dim_white, get_state_color, magenta, should_use_color
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


def lines_to_text(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def setup_output(args: object) -> bool:
    """Configure output settings and return color preference."""
    color_enabled = should_use_color(getattr(args, "color_flag", None))
    if color_enabled:
        colorama_init(autoreset=True, strip=False)
    return color_enabled


def apply_indent(lines: list[str], indent: str) -> list[str]:
    if not indent:
        return lines
    return [f"{indent}{line}" if line else "" for line in lines]


def section_header_lines(title: str, color_enabled: bool) -> list[str]:
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


def format_timeline_lines(
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
    return apply_indent([date_line, chart_line, underline], config.indent)


def format_tag_block(name: str, tag: Tag, config: TagBlockConfig) -> list[str]:
    lines: list[str] = []
    time_range = tag.time_range
    if time_range and time_range.earliest and time_range.timeline:
        earliest_date = select_earliest_date(config.date_from, config.global_timerange, time_range)
        latest_date = select_latest_date(config.date_until, config.global_timerange, time_range)
        if earliest_date and latest_date:
            lines.extend(
                format_timeline_lines(
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


def format_group_block(
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
            format_timeline_lines(
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

    lines = section_header_lines("GROUPS", color_enabled)

    if not filtered_groups:
        lines.append("  No results")
        return lines_to_text(apply_indent(lines, indent))

    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            lines.append("")
        lines.extend(
            format_group_block(
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

    return lines_to_text(apply_indent(lines, indent))


def format_top_tasks_section(
    nodes: list[orgparse.node.OrgNode],
    config: TopTasksSectionConfig,
) -> str:
    """Return formatted output for the top tasks section."""
    top_tasks = get_top_tasks(nodes, config.max_results)
    if not top_tasks:
        return ""

    lines = section_header_lines("TASKS", config.color_enabled)
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

    return lines_to_text(apply_indent(lines, config.indent))


def format_histogram_section(
    title: str,
    histogram: Histogram,
    config: HistogramSectionConfig,
) -> list[str]:
    lines = section_header_lines(title, config.render_config.color_enabled)
    histogram_lines = render_histogram(
        histogram,
        config.buckets,
        config.order,
        config.render_config,
    )
    lines.extend([f"  {line}" for line in histogram_lines])
    return apply_indent(lines, config.indent)
