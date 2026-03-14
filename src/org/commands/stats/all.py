"""Stats all command."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import orgparse
import typer
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from org import config as config_module
from org.analyze import AnalysisResult, Tag, TimeRange, analyze, clean
from org.analyze import Group as TagGroup
from org.cli_common import (
    CATEGORY_NAMES,
    get_top_tasks,
    load_and_process_data,
    resolve_date_filters,
    resolve_exclude_set,
    resolve_mapping,
)
from org.commands.stats.summary import SummaryDisplayConfig, format_tasks_summary
from org.tui import (
    GroupBlockConfig,
    TagBlockConfig,
    TaskLineConfig,
    TimelineFormatConfig,
    TopTasksSectionConfig,
    apply_indent,
    build_console,
    format_group_block,
    format_groups_section,
    format_tag_block,
    format_task_line,
    format_top_tasks_section,
    lines_to_text,
    processing_status,
    section_header_lines,
    setup_output,
)
from org.validation import validate_stats_arguments


@dataclass
class StatsAllArgs:
    """Arguments for the stats all command."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_keys: str
    done_keys: str
    filter_priority: str | None
    filter_level: int | None
    filter_repeats_above: int | None
    filter_repeats_below: int | None
    filter_date_from: str | None
    filter_date_until: str | None
    filter_properties: list[str] | None
    filter_tags: list[str] | None
    filter_headings: list[str] | None
    filter_bodies: list[str] | None
    filter_completed: bool
    filter_not_completed: bool
    color_flag: bool | None
    width: int | None
    max_results: int | None
    max_tags: int
    use: str
    with_tags_as_category: bool
    category_property: str
    max_relations: int
    min_group_size: int
    max_groups: int


@dataclass(frozen=True)
class _TaskDisplayConfig:
    """Configuration for rendering task rows in stats all layout."""

    color_enabled: bool
    done_keys: list[str]
    todo_keys: list[str]
    line_width: int


@dataclass(frozen=True)
class _GroupsDisplayConfig:
    """Configuration for rendering groups body in stats all layout."""

    plot_width: int
    date_from: datetime | None
    date_until: datetime | None
    global_timerange: TimeRange
    color_enabled: bool


@dataclass(frozen=True)
class _TagsDisplayConfig:
    """Configuration for rendering tags body in stats all layout."""

    exclude_set: set[str]
    date_from: datetime | None
    date_until: datetime | None
    global_timerange: TimeRange
    plot_width: int
    color_enabled: bool


@dataclass(frozen=True)
class _TagsSectionConfig:
    """Configuration for rendering a single tags section."""

    max_relations: int
    plot_width: int
    date_from: datetime | None
    date_until: datetime | None
    global_timerange: TimeRange
    max_items: int
    exclude_set: set[str]
    color_enabled: bool


@dataclass(frozen=True)
class _StatsAllDisplayConfig:
    """Configuration shared across stats all layout sections."""

    exclude_set: set[str]
    date_from: datetime | None
    date_until: datetime | None
    done_keys: list[str]
    todo_keys: list[str]
    color_enabled: bool


@dataclass(frozen=True)
class _StatsAllPanelSection:
    """Panel section content for stats all layouts."""

    title: str
    body: str


@dataclass(frozen=True)
class _StatsAllSectionBuildConfig:
    """Configuration for building stats all panel sections."""

    panel_content_width: int
    use_summary_based_default: bool


def format_tags_section(
    category_name: str,
    tags: dict[str, Tag],
    config: _TagsSectionConfig,
    order_fn: Callable[[tuple[str, Tag]], int],
    indent: str = "",
) -> str:
    """Return formatted output for a single tags section."""
    if config.max_items == 0:
        return ""

    cleaned = clean(config.exclude_set, tags)
    sorted_items = sorted(cleaned.items(), key=order_fn)[0 : config.max_items]

    lines = section_header_lines(category_name.upper(), config.color_enabled)

    if not sorted_items:
        lines.append("  No results")
        return lines_to_text(apply_indent(lines, indent))

    for idx, (name, tag) in enumerate(sorted_items):
        if idx > 0:
            lines.append("")
        lines.extend(
            format_tag_block(
                name,
                tag,
                TagBlockConfig(
                    max_relations=config.max_relations,
                    exclude_set=config.exclude_set,
                    date_from=config.date_from,
                    date_until=config.date_until,
                    global_timerange=config.global_timerange,
                    timeline=TimelineFormatConfig(
                        color_enabled=config.color_enabled,
                        indent="  ",
                        plot_width=config.plot_width,
                    ),
                    name_indent="  ",
                    stats_indent="    ",
                ),
            )
        )

    return lines_to_text(apply_indent(lines, indent))


def format_stats_all_output(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: StatsAllArgs,
    display_config: _StatsAllDisplayConfig,
    plot_width: int,
) -> str:
    """Return formatted output for the stats all command."""

    def order_by_total(item: tuple[str, Tag]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total_tasks

    category_name = CATEGORY_NAMES[args.use]
    task_limit = args.max_results if args.max_results is not None else 10

    return "".join(
        section
        for section in (
            format_tasks_summary(
                result,
                SummaryDisplayConfig(
                    date_from=display_config.date_from,
                    date_until=display_config.date_until,
                    done_keys=display_config.done_keys,
                    todo_keys=display_config.todo_keys,
                    color_enabled=display_config.color_enabled,
                ),
                plot_width,
            ),
            format_top_tasks_section(
                nodes,
                TopTasksSectionConfig(
                    max_results=task_limit,
                    color_enabled=display_config.color_enabled,
                    done_keys=display_config.done_keys,
                    todo_keys=display_config.todo_keys,
                    line_width=plot_width,
                    indent="",
                ),
            ),
            format_tags_section(
                category_name,
                result.tags,
                _TagsSectionConfig(
                    max_relations=args.max_relations,
                    plot_width=plot_width,
                    date_from=display_config.date_from,
                    date_until=display_config.date_until,
                    global_timerange=result.timerange,
                    max_items=args.max_tags,
                    exclude_set=display_config.exclude_set,
                    color_enabled=display_config.color_enabled,
                ),
                order_by_total,
                indent="  ",
            ),
            format_groups_section(
                result.tag_groups,
                display_config.exclude_set,
                (
                    args.min_group_size,
                    plot_width,
                    display_config.date_from,
                    display_config.date_until,
                    result.timerange,
                    display_config.color_enabled,
                ),
                args.max_groups,
                indent="  ",
            ),
        )
        if section
    )


def _line_count(text: str) -> int:
    """Return visual line count for preformatted text blocks."""
    normalized = text.strip("\n")
    if not normalized:
        return 1
    return len(normalized.splitlines())


def _panel_body(text: str, color_enabled: bool) -> Text:
    """Return non-wrapping panel body text."""
    panel_text = Text.from_markup(text) if color_enabled else Text(text)
    panel_text.no_wrap = True
    panel_text.overflow = "ignore"
    return panel_text


def _normalize_panel_body(text: str) -> str:
    """Normalize section body text for panel rendering."""
    return text.rstrip("\n") or "No results"


def _section_height(section: _StatsAllPanelSection) -> int:
    """Return panel height for a section body."""
    return _line_count(section.body) + 2


def _resolve_stats_all_task_limit(
    max_results: int | None,
    normalized_summary_body: str,
    use_summary_based_default: bool,
) -> int:
    """Resolve effective task limit for stats all layouts."""
    if max_results is not None:
        return max_results
    if use_summary_based_default:
        return max(1, _line_count(normalized_summary_body))
    return 10


def _build_panel(
    section: _StatsAllPanelSection, color_enabled: bool, height: int | None = None
) -> Panel:
    """Create a Panel for a section using shared config."""
    panel_height = _section_height(section) if height is None else height
    return Panel(
        _panel_body(section.body, color_enabled),
        title=section.title,
        expand=True,
        height=panel_height,
    )


def _build_stats_all_panel_sections(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: StatsAllArgs,
    display_config: _StatsAllDisplayConfig,
    config: _StatsAllSectionBuildConfig,
) -> list[_StatsAllPanelSection]:
    """Build panel sections shared by both stats all layout modes."""
    summary_body = format_tasks_summary(
        result,
        SummaryDisplayConfig(
            date_from=display_config.date_from,
            date_until=display_config.date_until,
            done_keys=display_config.done_keys,
            todo_keys=display_config.todo_keys,
            color_enabled=display_config.color_enabled,
        ),
        config.panel_content_width,
    )
    normalized_summary_body = _normalize_panel_body(summary_body)
    task_limit = _resolve_stats_all_task_limit(
        args.max_results,
        normalized_summary_body,
        config.use_summary_based_default,
    )
    tasks_body = _format_tasks_body(
        nodes,
        task_limit,
        _TaskDisplayConfig(
            color_enabled=display_config.color_enabled,
            done_keys=display_config.done_keys,
            todo_keys=display_config.todo_keys,
            line_width=config.panel_content_width,
        ),
    )

    sections = [
        _StatsAllPanelSection(title="SUMMARY", body=normalized_summary_body),
        _StatsAllPanelSection(title="TASKS", body=_normalize_panel_body(tasks_body)),
    ]

    if args.max_tags != 0:
        tags_body = _format_tags_body(
            result.tags,
            args,
            _TagsDisplayConfig(
                exclude_set=display_config.exclude_set,
                date_from=display_config.date_from,
                date_until=display_config.date_until,
                global_timerange=result.timerange,
                plot_width=config.panel_content_width,
                color_enabled=display_config.color_enabled,
            ),
        )
        sections.append(
            _StatsAllPanelSection(
                title=CATEGORY_NAMES[args.use].upper(),
                body=_normalize_panel_body(tags_body),
            )
        )

    if args.max_groups != 0:
        groups_body = _format_groups_body(
            result.tag_groups,
            display_config.exclude_set,
            args.min_group_size,
            args.max_groups,
            _GroupsDisplayConfig(
                plot_width=config.panel_content_width,
                date_from=display_config.date_from,
                date_until=display_config.date_until,
                global_timerange=result.timerange,
                color_enabled=display_config.color_enabled,
            ),
        )
        sections.append(
            _StatsAllPanelSection(title="GROUPS", body=_normalize_panel_body(groups_body))
        )

    return sections


def _format_tasks_body(
    nodes: list[orgparse.node.OrgNode],
    max_results: int,
    config: _TaskDisplayConfig,
) -> str:
    """Return tasks body text without section header."""
    top_tasks = get_top_tasks(nodes, max_results)
    if not top_tasks:
        return "No results\n"

    lines = [
        format_task_line(
            node,
            TaskLineConfig(
                color_enabled=config.color_enabled,
                done_keys=config.done_keys,
                todo_keys=config.todo_keys,
                line_width=config.line_width,
            ),
            indent="",
        )
        for node in top_tasks
    ]
    return lines_to_text(lines)


_TWO_COLUMN_MIN_WIDTH = 120


def _resolve_two_column_panel_content_width(console_width: int) -> int:
    """Resolve per-column panel body width for two-column stats all layout."""
    left_column_width = max(25, console_width // 2)
    right_column_width = max(25, console_width - left_column_width)
    min_column_width = min(left_column_width, right_column_width)

    # Rich Panel uses one-cell borders and one-cell horizontal padding on each side.
    panel_chrome_width = 4
    return max(20, min_column_width - panel_chrome_width)


def _resolve_single_column_panel_content_width(console_width: int) -> int:
    """Resolve panel body width for single-column stats all layout."""
    panel_chrome_width = 4
    return max(20, console_width - panel_chrome_width)


def _format_tags_body(
    tags: dict[str, Tag],
    args: StatsAllArgs,
    config: _TagsDisplayConfig,
) -> str:
    """Return tags body without section header."""
    if args.max_tags == 0:
        return ""

    cleaned = clean(config.exclude_set, tags)
    sorted_items = sorted(cleaned.items(), key=lambda item: -item[1].total_tasks)[0 : args.max_tags]
    lines: list[str] = []

    if not sorted_items:
        lines.append("No results")
        return lines_to_text(lines)

    for idx, (name, tag) in enumerate(sorted_items):
        if lines and lines[-1] != "":
            lines.append("")
        if idx > 0:
            lines.append("")
        lines.extend(
            format_tag_block(
                name,
                tag,
                TagBlockConfig(
                    max_relations=args.max_relations,
                    exclude_set=config.exclude_set,
                    date_from=config.date_from,
                    date_until=config.date_until,
                    global_timerange=config.global_timerange,
                    timeline=TimelineFormatConfig(
                        color_enabled=config.color_enabled,
                        indent="",
                        plot_width=config.plot_width,
                    ),
                    name_indent="",
                    stats_indent="  ",
                ),
            )
        )

    return lines_to_text(lines)


def _render_single_column_stats_all_layout(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: StatsAllArgs,
    display_config: _StatsAllDisplayConfig,
    console_width: int,
) -> tuple[Layout, int]:
    """Build a single-column stats all layout with vertically stacked sections."""
    panel_content_width = _resolve_single_column_panel_content_width(console_width)
    sections = _build_stats_all_panel_sections(
        result,
        nodes,
        args,
        display_config,
        _StatsAllSectionBuildConfig(
            panel_content_width=panel_content_width,
            use_summary_based_default=False,
        ),
    )

    root = Layout(name="root")
    section_heights = [_section_height(section) for section in sections]
    section_layouts = [
        Layout(
            _build_panel(section, display_config.color_enabled, height=height),
            size=height,
        )
        for section, height in zip(sections, section_heights, strict=True)
    ]
    total_height = sum(section_heights)
    root.size = total_height
    root.split_column(*section_layouts)
    return root, total_height


def render_stats_all_layout(
    console: Console,
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: StatsAllArgs,
    display_config: _StatsAllDisplayConfig,
) -> tuple[Layout, int]:
    """Build a two-column stats all layout using Rich Layout and Panels."""
    if console.width < _TWO_COLUMN_MIN_WIDTH:
        return _render_single_column_stats_all_layout(
            result, nodes, args, display_config, console.width
        )

    panel_content_width = _resolve_two_column_panel_content_width(console.width)
    sections = _build_stats_all_panel_sections(
        result,
        nodes,
        args,
        display_config,
        _StatsAllSectionBuildConfig(
            panel_content_width=panel_content_width,
            use_summary_based_default=True,
        ),
    )
    summary_section = sections[0]
    tasks_section = sections[1]

    top_panel_height = max(_section_height(summary_section), _section_height(tasks_section))

    top_layout = Layout(name="top")
    top_layout.size = top_panel_height
    top_layout.split_row(
        Layout(
            _build_panel(summary_section, display_config.color_enabled, height=top_panel_height),
            ratio=1,
        ),
        Layout(
            _build_panel(tasks_section, display_config.color_enabled, height=top_panel_height),
            ratio=1,
        ),
    )

    bottom_sections = sections[2:]
    if not bottom_sections:
        root = Layout(name="root")
        root.size = top_panel_height
        root.update(top_layout)
        return root, top_panel_height

    bottom_left = _build_panel(bottom_sections[0], display_config.color_enabled)
    bottom_right: Panel | str = ""
    if len(bottom_sections) > 1:
        bottom_right = _build_panel(bottom_sections[1], display_config.color_enabled)

    bottom_layout = Layout(name="bottom")
    bottom_layout.size = max(_section_height(section) for section in bottom_sections)
    bottom_layout.split_row(
        Layout(bottom_left, ratio=1),
        Layout(bottom_right, ratio=1),
    )

    total_height = top_panel_height + bottom_layout.size
    root = Layout(name="root")
    root.size = total_height
    root.split_column(top_layout, bottom_layout)
    return root, total_height


def _format_groups_body(
    groups: list[TagGroup],
    exclude_set: set[str],
    min_group_size: int,
    max_groups: int,
    config: _GroupsDisplayConfig,
) -> str:
    """Return groups body without section header."""
    if max_groups == 0:
        return ""

    filtered_groups: list[tuple[list[str], TagGroup]] = []
    for group in groups:
        filtered_tags = [tag for tag in group.tags if tag not in exclude_set]
        if len(filtered_tags) >= min_group_size:
            filtered_groups.append((filtered_tags, group))

    filtered_groups.sort(key=lambda item: len(item[0]), reverse=True)
    filtered_groups = filtered_groups[:max_groups]
    if not filtered_groups:
        return "No results\n"

    lines: list[str] = []
    for idx, (group_tags, group) in enumerate(filtered_groups):
        if idx > 0:
            lines.append("")
        lines.extend(
            format_group_block(
                group_tags,
                group,
                GroupBlockConfig(
                    date_from=config.date_from,
                    date_until=config.date_until,
                    global_timerange=config.global_timerange,
                    timeline=TimelineFormatConfig(
                        color_enabled=config.color_enabled,
                        indent="",
                        plot_width=config.plot_width,
                    ),
                    name_indent="",
                    stats_indent="  ",
                ),
            )
        )

    return lines_to_text(lines)


def run_stats(args: StatsAllArgs) -> None:
    """Run the stats command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)
    validate_stats_arguments(args)
    layout: Layout | None = None
    layout_height = 0

    with processing_status(console, color_enabled):
        mapping = resolve_mapping(args)
        exclude_set = resolve_exclude_set(args)
        nodes, todo_keys, done_keys = load_and_process_data(args)
        if nodes:
            result = analyze(nodes, mapping, args.use, args.max_relations, args.category_property)
            date_from, date_until = resolve_date_filters(args)
            layout, layout_height = render_stats_all_layout(
                console,
                result,
                nodes,
                args,
                _StatsAllDisplayConfig(
                    exclude_set=exclude_set,
                    date_from=date_from,
                    date_until=date_until,
                    done_keys=done_keys,
                    todo_keys=todo_keys,
                    color_enabled=color_enabled,
                ),
            )

    if not nodes or layout is None:
        console.print("No results", markup=False)
        return

    console.height = max(layout_height, 1)
    console.print(layout)


def register(app: typer.Typer) -> None:
    """Register the stats all command."""

    @app.command("all", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
    def stats_all(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None, metavar="FILE", help="Org-mode archive files or directories to analyze"
        ),
        config: str = typer.Option(
            ".org-cli.json",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        exclude: str | None = typer.Option(
            None,
            "--exclude",
            metavar="FILE",
            help="File containing words to exclude (one per line)",
        ),
        mapping: str | None = typer.Option(
            None,
            "--mapping",
            metavar="FILE",
            help="JSON file containing tag mappings (dict[str, str])",
        ),
        todo_keys: str = typer.Option(
            "TODO",
            "--todo-keys",
            metavar="KEYS",
            help="Comma-separated list of incomplete task states",
        ),
        done_keys: str = typer.Option(
            "DONE",
            "--done-keys",
            metavar="KEYS",
            help="Comma-separated list of completed task states",
        ),
        filter_priority: str | None = typer.Option(
            None,
            "--filter-priority",
            metavar="P",
            help="Filter tasks where priority equals P",
        ),
        filter_level: int | None = typer.Option(
            None,
            "--filter-level",
            metavar="N",
            help="Filter tasks where heading level equals N",
        ),
        filter_repeats_above: int | None = typer.Option(
            None,
            "--filter-repeats-above",
            metavar="N",
            help="Filter tasks where repeat count > N (non-inclusive)",
        ),
        filter_repeats_below: int | None = typer.Option(
            None,
            "--filter-repeats-below",
            metavar="N",
            help="Filter tasks where repeat count < N (non-inclusive)",
        ),
        filter_date_from: str | None = typer.Option(
            None,
            "--filter-date-from",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps after date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_date_until: str | None = typer.Option(
            None,
            "--filter-date-until",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps before date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_properties: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-property",
            metavar="KEY=VALUE",
            help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
        ),
        filter_tags: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-tag",
            metavar="REGEX",
            help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
        ),
        filter_headings: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-heading",
            metavar="REGEX",
            help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
        ),
        filter_bodies: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-body",
            metavar="REGEX",
            help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
        ),
        filter_completed: bool = typer.Option(
            False,
            "--filter-completed",
            help="Filter tasks with todo state in done keys",
        ),
        filter_not_completed: bool = typer.Option(
            False,
            "--filter-not-completed",
            help="Filter tasks with todo state in todo keys or without a todo state",
        ),
        color_flag: bool | None = typer.Option(
            None,
            "--color/--no-color",
            help="Force colored output",
        ),
        width: int | None = typer.Option(
            None,
            "--width",
            metavar="N",
            min=50,
            help="Override auto-derived console width (minimum: 50)",
        ),
        max_results: int | None = typer.Option(
            None,
            "--limit",
            "-n",
            metavar="N",
            help="Maximum number of results to display",
        ),
        max_tags: int = typer.Option(
            5,
            "--max-tags",
            metavar="N",
            help="Maximum number of tags to display in TAGS section (use 0 to omit section)",
        ),
        use: str = typer.Option(
            "tags",
            "--use",
            metavar="CATEGORY",
            help="Category to display: tags, heading, or body",
        ),
        with_tags_as_category: bool = typer.Option(
            False,
            "--with-tags-as-category",
            help="Preprocess nodes to set category property based on first tag",
        ),
        category_property: str = typer.Option(
            "CATEGORY",
            "--category-property",
            metavar="PROPERTY",
            help="Property name to use for category histogram and filtering",
        ),
        max_relations: int = typer.Option(
            5,
            "--max-relations",
            metavar="N",
            help="Maximum number of relations to display per item (use 0 to omit sections)",
        ),
        min_group_size: int = typer.Option(
            2,
            "--min-group-size",
            metavar="N",
            help="Minimum group size to display",
        ),
        max_groups: int = typer.Option(
            5,
            "--max-groups",
            metavar="N",
            help="Maximum number of tag groups to display (use 0 to omit section)",
        ),
    ) -> None:
        """Show overall task stats."""
        args = StatsAllArgs(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=None,
            exclude_inline=None,
            todo_keys=todo_keys,
            done_keys=done_keys,
            filter_priority=filter_priority,
            filter_level=filter_level,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            width=width,
            max_results=max_results,
            max_tags=max_tags,
            use=use,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=min_group_size,
            max_groups=max_groups,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "stats all")
        config_module.log_command_arguments(args, "stats all")
        run_stats(args)
