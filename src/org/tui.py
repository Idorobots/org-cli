"""Terminal output formatting for the org CLI."""

from __future__ import annotations

import textwrap
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from org_parser.text import (
    AngleLink,
    Bold,
    Code,
    InlineBabelCall,
    InlineObject,
    InlineSourceBlock,
    Italic,
    LineBreak,
    PlainLink,
    PlainText,
    RegularLink,
    RichText,
    StrikeThrough,
    Subscript,
    Superscript,
    Underline,
    Verbatim,
)
from rich.cells import cell_len
from rich.console import Console
from rich.style import Style
from rich.text import Text

from org.cli_common import get_top_tasks
from org.color import (
    bright_blue,
    bright_white,
    colorize,
    dim_white,
    escape_text,
    get_state_color,
    magenta,
    should_use_color,
)
from org.histogram import (
    Histogram,
    HistogramRenderConfig,
    RenderConfig,
    render_histogram,
    visual_len,
)
from org.plot import TimelineRenderConfig, render_timeline_chart


if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import date, datetime

    from org_parser.document import Heading

    from org.analyze import Group, Tag, TimeRange


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
    """Join rendered lines into one newline-terminated text block."""
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def setup_output(args: object) -> bool:
    """Configure output settings and return color preference."""
    return should_use_color(getattr(args, "color_flag", None))


def build_console(color_enabled: bool, width: int | None = None) -> Console:
    """Create a Rich console configured for colored output."""
    return Console(no_color=not color_enabled, force_terminal=color_enabled, width=width)


def print_output(console: Console, text: str, color_enabled: bool, *, end: str = "\n") -> None:
    """Print output without Rich line wrapping."""
    if color_enabled:
        rich_text = Text.from_markup(text)
        rich_text.no_wrap = True
        rich_text.overflow = "ignore"
        console.print(rich_text, end=end, soft_wrap=True)
        return
    plain_text = Text(text)
    plain_text.no_wrap = True
    plain_text.overflow = "ignore"
    console.print(plain_text, end=end, markup=False, soft_wrap=True)


@contextmanager
def processing_status(console: Console, color_enabled: bool) -> Iterator[None]:
    """Show a processing spinner when color output is enabled."""
    if color_enabled:
        with console.status("Processing...", spinner="dots", spinner_style="white"):
            yield
        return
    yield


def apply_indent(lines: list[str], indent: str) -> list[str]:
    """Prefix non-empty lines with the requested indentation."""
    if not indent:
        return lines
    return [f"{indent}{line}" if line else "" for line in lines]


def section_header_lines(title: str, color_enabled: bool) -> list[str]:
    """Build standard section header lines."""
    return ["", bright_white(title, color_enabled)]


@dataclass(frozen=True)
class TimelineFormatConfig:
    """Configuration for rendering timeline charts."""

    color_enabled: bool
    indent: str
    plot_width: int


def resolve_timeline_plot_width(config: TimelineFormatConfig) -> int:
    """Resolve visual timeline plot width from config."""
    return max(3, config.plot_width)


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

    plot_width: int
    order: list[str]
    render_config: RenderConfig
    indent: str


@dataclass(frozen=True)
class TopTasksSectionConfig:
    """Configuration for rendering the top tasks section."""

    max_results: int
    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]
    indent: str
    line_width: int | None = None


@dataclass(frozen=True)
class TaskLineConfig:
    """Configuration for rendering a single task line."""

    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]
    line_width: int | None = None


@dataclass(frozen=True)
class _TaskLineParts:
    """Internal data structure for task line components."""

    colored_filename: str
    level_prefix: str
    colored_state: str
    priority_text: str
    heading: str
    heading_text: Text


def _truncate_filename(filename: str, width: int) -> str:
    """Truncate or pad filename to fixed-width column."""
    truncated = _truncate_to_visual_width(filename, width)
    return _pad_to_visual_width(truncated, width)


def _truncate_to_visual_width(text: str, max_width: int) -> str:
    """Return text truncated to visual display width."""
    if max_width <= 0:
        return ""

    current = ""
    for char in text:
        candidate = f"{current}{char}"
        if visual_len(candidate) > max_width:
            break
        current = candidate
    return current


def _pad_to_visual_width(text: str, width: int) -> str:
    """Right-pad text to target visual display width."""
    missing_width = width - visual_len(text)
    if missing_width <= 0:
        return text
    return f"{text}{' ' * missing_width}"


def _render_text_for_output(text: Text, color_enabled: bool) -> str:
    """Render Rich Text either as markup or plain string."""
    if color_enabled:
        return text.markup
    return text.plain


def _truncate_rich_text_to_visual_width(text: Text, max_width: int) -> Text:
    """Truncate Rich Text to visual width while preserving style spans."""
    if max_width <= 0:
        return Text("")
    truncated = text.copy()
    truncated.truncate(max_width, overflow="crop")
    return truncated


def _append_styled_inline_body(output: Text, body: list[InlineObject], style: str) -> None:
    """Append inline body and apply one style span over it."""
    start = len(output)
    output.append_text(_inline_parts_to_text(body))
    if len(output) > start:
        output.stylize(style, start, len(output))


def _append_link_text(output: Text, link_text: Text, target: str) -> None:
    """Append link text and annotate it with a Rich link target."""
    start = len(output)
    output.append_text(link_text)
    if target and len(output) > start:
        output.stylize(Style(link=target), start, len(output))


def _append_regular_link(output: Text, link: RegularLink) -> None:
    """Append one regular link object."""
    target = link.path
    if link.description is None:
        link_text = Text(target)
    else:
        link_text = _inline_parts_to_text(link.description)
    _append_link_text(output, link_text, target)


_STYLE_BY_MARKUP_TYPE: dict[type[InlineObject], str] = {
    Bold: "bold",
    Italic: "italic",
    Underline: "underline",
    StrikeThrough: "strike",
}


def _append_inline_part(output: Text, part: InlineObject) -> None:
    """Append one org_parser inline object as Rich text."""
    if isinstance(part, PlainText):
        output.append(part.text)
    elif isinstance(part, Bold | Italic | Underline | StrikeThrough):
        style = _STYLE_BY_MARKUP_TYPE[type(part)]
        _append_styled_inline_body(output, part.body, style)
    elif isinstance(part, Verbatim | Code):
        output.append(part.body, style="dim")
    elif isinstance(part, InlineSourceBlock | InlineBabelCall):
        output.append(str(part), style="dim")
    elif isinstance(part, RegularLink):
        _append_regular_link(output, part)
    elif isinstance(part, PlainLink):
        target = f"{part.link_type}:{part.path}"
        _append_link_text(output, Text(target), target)
    elif isinstance(part, AngleLink):
        target = f"{part.link_type}:{part.path}" if part.link_type else part.path
        _append_link_text(output, Text(target), target)
    elif isinstance(part, Superscript | Subscript | LineBreak):
        output.append(str(part))
    else:
        output.append(str(part))


def _inline_parts_to_text(parts: list[InlineObject]) -> Text:
    """Convert org_parser inline objects into Rich Text spans."""
    output = Text()
    for part in parts:
        _append_inline_part(output, part)
    return output


def _heading_to_text(node: Heading) -> Text:
    """Render heading title from rich title parts when available."""
    title = getattr(node, "title", None)
    if isinstance(title, RichText):
        return _inline_parts_to_text(title.trimmed.parts)

    heading = node.title_text.strip() if node.title_text else ""
    return Text(heading)


def heading_title_to_text(node: Heading) -> Text:
    """Return heading title rendered as Rich Text spans."""
    return _heading_to_text(node)


def task_state_prefix_to_text(
    state: str,
    *,
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> Text:
    """Return TODO state prefix as styled Rich Text."""
    if not state:
        return Text("")
    style = get_state_color(state, done_states, todo_states, color_enabled)
    return Text(f"{state} ", style=style or "")


def task_priority_to_text(
    priority: str | None,
    color_enabled: bool,
    *,
    trailing_space: bool = False,
) -> Text:
    """Return task priority marker as styled Rich Text."""
    if not priority:
        return Text("")
    suffix = " " if trailing_space else ""
    return Text(f"[#{priority}]{suffix}", style="bold blue" if color_enabled else "")


def task_tags_to_text(tags: list[str], color_enabled: bool) -> Text:
    """Return task tags as styled Rich Text."""
    if not tags:
        return Text("")
    tags_text = f":{':'.join(sorted(tags))}:"
    return Text(tags_text, style="dim white" if color_enabled else "")


def _build_task_line_parts(node: Heading, config: TaskLineConfig) -> _TaskLineParts:
    """Extract and format task line components."""
    filename = node.document.filename or "<string>"
    filename_cell = _truncate_filename(filename, 15)
    colored_filename = dim_white(filename_cell, config.color_enabled)
    todo_state = node.todo or ""
    heading_text = heading_title_to_text(node)
    heading = _render_text_for_output(heading_text, config.color_enabled)
    level = node.level if node.level is not None else 0
    level_prefix = "*" * level if level > 0 else ""

    priority_text = ""
    if node.priority:
        priority_display = f"[#{node.priority}]"
        priority_text = f" {bright_blue(priority_display, config.color_enabled)}"

    colored_state = ""
    if todo_state:
        state_style = get_state_color(
            todo_state,
            config.done_states,
            config.todo_states,
            config.color_enabled,
        )
        if config.color_enabled and state_style:
            colored_state = colorize(todo_state, state_style, config.color_enabled)
        else:
            colored_state = todo_state

    return _TaskLineParts(
        colored_filename,
        level_prefix,
        colored_state,
        priority_text,
        heading,
        heading_text,
    )


def _format_line_with_parts(parts: _TaskLineParts) -> str:
    """Build formatted line from components."""
    if parts.colored_state:
        body = (
            f"{parts.level_prefix} {parts.colored_state}{parts.priority_text} {parts.heading}"
        ).strip()
        return f"{parts.colored_filename}{body}"
    if parts.priority_text:
        body = f"{parts.level_prefix}{parts.priority_text} {parts.heading}".strip()
        return f"{parts.colored_filename}{body}"
    body = f"{parts.level_prefix} {parts.heading}".strip()
    return f"{parts.colored_filename}{body}"


def _resolve_task_line_width(config: TaskLineConfig, line: str) -> int:
    """Resolve task line width used for right-aligned tags."""
    if config.line_width is not None:
        return config.line_width
    return visual_len(line)


def _add_tags_to_line(
    line: str,
    node: Heading,
    parts: _TaskLineParts,
    config: TaskLineConfig,
) -> str:
    """Add tags to line with alignment and heading truncation."""
    sorted_tags = sorted(node.tags)
    tags_text = f":{':'.join(sorted_tags)}:"
    colored_tags = dim_white(tags_text, config.color_enabled)

    line_width = _resolve_task_line_width(config, line)
    line_visual_len = visual_len(line)
    tags_visual_len = visual_len(tags_text)
    available_space = line_width - tags_visual_len

    if line_visual_len > available_space:
        heading_visual_len = cell_len(parts.heading_text.plain)
        target_heading_visual_len = heading_visual_len - (line_visual_len - available_space)
        if target_heading_visual_len > 0:
            truncated_heading_text = _truncate_rich_text_to_visual_width(
                parts.heading_text,
                target_heading_visual_len,
            )
            truncated_heading = _render_text_for_output(
                truncated_heading_text,
                config.color_enabled,
            )
            truncated_parts = _TaskLineParts(
                parts.colored_filename,
                parts.level_prefix,
                parts.colored_state,
                parts.priority_text,
                truncated_heading,
                truncated_heading_text,
            )
            line = _format_line_with_parts(truncated_parts)

    line_visual_len = visual_len(line)
    if line_visual_len < line_width:
        padding = " " * (line_width - line_visual_len - tags_visual_len)
        return f"{line}{padding}{colored_tags}"
    return f"{line} {colored_tags}"


def format_task_line(
    node: Heading,
    config: TaskLineConfig,
    indent: str = "",
) -> str:
    """Return formatted task line for list output."""
    parts = _build_task_line_parts(node, config)
    line = _format_line_with_parts(parts)

    if node.tags and config.line_width is not None:
        line = _add_tags_to_line(line, node, parts, config)

    if indent:
        return f"{indent}{line}" if line else indent
    return line


def format_timeline_lines(
    timeline: dict[date, int],
    earliest_date: date,
    latest_date: date,
    config: TimelineFormatConfig,
) -> list[str]:
    """Render timeline chart lines and apply configured indentation."""
    plot_width = resolve_timeline_plot_width(config)
    date_line, chart_line, underline = render_timeline_chart(
        timeline,
        earliest_date,
        latest_date,
        TimelineRenderConfig(
            plot_width=plot_width,
            color_enabled=config.color_enabled,
        ),
    )
    return apply_indent([date_line, chart_line, underline], config.indent)


def format_tag_block(name: str, tag: Tag, config: TagBlockConfig) -> list[str]:
    """Render one tag block with timeline, stats, and relation lines."""
    lines: list[str] = []
    color_enabled = config.timeline.color_enabled
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
                ),
            )

    display_name = escape_text(name, color_enabled)
    lines.append(f"{config.name_indent}{display_name}")
    total_tasks_value = magenta(str(tag.total_tasks), color_enabled)
    lines.append(f"{config.stats_indent}Total tasks: {total_tasks_value}")
    if tag.time_range.earliest and tag.time_range.latest:
        avg_value = magenta(f"{tag.avg_tasks_per_day:.2f}", color_enabled)
        max_value = magenta(str(tag.max_single_day_count), color_enabled)
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
                    f"{relation_indent}{escape_text(related_name, color_enabled)} ({count})"
                    for related_name, count in sorted_relations
                ],
            )
    return lines


def format_group_block(
    group_tags: list[str],
    group: Group,
    config: GroupBlockConfig,
) -> list[str]:
    """Render one group block with timeline and aggregate statistics."""
    lines: list[str] = []
    color_enabled = config.timeline.color_enabled
    earliest_date = select_earliest_date(
        config.date_from,
        config.global_timerange,
        group.time_range,
    )
    latest_date = select_latest_date(config.date_until, config.global_timerange, group.time_range)
    if earliest_date and latest_date:
        lines.extend(
            format_timeline_lines(
                group.time_range.timeline,
                earliest_date,
                latest_date,
                config.timeline,
            ),
        )

    max_name_width = max(1, config.timeline.plot_width - visual_len(config.name_indent))
    display_tags = ", ".join(group_tags)
    wrapped_tags = textwrap.wrap(
        display_tags,
        width=max_name_width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    lines.extend(
        [
            f"{config.name_indent}{escape_text(wrapped_line, color_enabled)}"
            for wrapped_line in wrapped_tags or [""]
        ],
    )
    total_tasks_value = magenta(str(group.total_tasks), color_enabled)
    avg_value = magenta(f"{group.avg_tasks_per_day:.2f}", color_enabled)
    max_value = magenta(str(group.max_single_day_count), color_enabled)
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

    min_group_size, plot_width, date_from, date_until, global_timerange, color_enabled = config

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
                        color_enabled=color_enabled,
                        indent="  ",
                        plot_width=plot_width,
                    ),
                    name_indent="  ",
                    stats_indent="    ",
                ),
            ),
        )

    return lines_to_text(apply_indent(lines, indent))


def format_top_tasks_section(
    nodes: list[Heading],
    config: TopTasksSectionConfig,
) -> str:
    """Return formatted output for the top tasks section."""
    top_tasks = get_top_tasks(nodes, config.max_results)
    if not top_tasks:
        return ""

    lines = [
        format_task_line(
            node,
            TaskLineConfig(
                color_enabled=config.color_enabled,
                done_states=config.done_states,
                todo_states=config.todo_states,
                line_width=config.line_width,
            ),
            indent="  ",
        )
        for node in top_tasks
    ]

    return lines_to_text(apply_indent(lines, config.indent))


def format_histogram_section(
    title: str,
    histogram: Histogram,
    config: HistogramSectionConfig,
) -> list[str]:
    """Render one histogram section as indented output lines."""
    lines = section_header_lines(title, config.render_config.color_enabled)
    histogram_plot_width = max(3, config.plot_width - 2)
    histogram_lines = render_histogram(
        histogram,
        HistogramRenderConfig(
            plot_width=histogram_plot_width,
            category_order=config.order,
            style=config.render_config,
        ),
    )
    lines.extend([f"  {line}" for line in histogram_lines])
    return apply_indent(lines, config.indent)
