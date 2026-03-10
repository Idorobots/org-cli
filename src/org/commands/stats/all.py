"""Stats all command."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from io import StringIO

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
from org.commands.stats.summary import format_tasks_summary
from org.tui import (
    TagBlockConfig,
    TaskLineConfig,
    TimelineFormatConfig,
    TopTasksSectionConfig,
    apply_indent,
    build_console,
    format_groups_section,
    format_tag_block,
    format_task_line,
    format_top_tasks_section,
    lines_to_text,
    print_output,
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
    max_results: int
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


def format_tags_section(
    category_name: str,
    tags: dict[str, Tag],
    config: tuple[int, int, int, datetime | None, datetime | None, TimeRange, int, set[str], bool],
    order_fn: Callable[[tuple[str, Tag]], int],
    indent: str = "",
) -> str:
    """Return formatted output for a single tags section."""
    (
        _max_results,
        max_relations,
        plot_width,
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

    lines = section_header_lines(category_name.upper(), color_enabled)

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
                    max_relations=max_relations,
                    exclude_set=exclude_set,
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
            )
        )

    return lines_to_text(apply_indent(lines, indent))


def format_stats_all_output(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: StatsAllArgs,
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str], bool],
    plot_width: int,
) -> str:
    """Return formatted output for the stats all command."""
    exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled = display_config

    def order_by_total(item: tuple[str, Tag]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total_tasks

    category_name = CATEGORY_NAMES[args.use]

    return "".join(
        section
        for section in (
            format_tasks_summary(
                result,
                (date_from, date_until, done_keys, todo_keys, color_enabled),
                plot_width,
            ),
            format_top_tasks_section(
                nodes,
                TopTasksSectionConfig(
                    max_results=args.max_results,
                    color_enabled=color_enabled,
                    done_keys=done_keys,
                    todo_keys=todo_keys,
                    line_width=plot_width,
                    indent="",
                ),
            ),
            format_tags_section(
                category_name,
                result.tags,
                (
                    args.max_results,
                    args.max_relations,
                    plot_width,
                    date_from,
                    date_until,
                    result.timerange,
                    args.max_tags,
                    exclude_set,
                    color_enabled,
                ),
                order_by_total,
                indent="  ",
            ),
            format_groups_section(
                result.tag_groups,
                exclude_set,
                (
                    args.min_group_size,
                    plot_width,
                    date_from,
                    date_until,
                    result.timerange,
                    color_enabled,
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


def _dedent_section_body(text: str, *, drop_title: bool) -> str:
    """Normalize section body lines and optionally drop title line."""
    body_lines = text.splitlines()
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]
    if drop_title and body_lines:
        body_lines = body_lines[1:]
    unindented_lines = [line.lstrip() if line else "" for line in body_lines]
    if not unindented_lines:
        return ""
    return "\n".join(unindented_lines) + "\n"


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


def _render_single_column_stats_all_layout(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: StatsAllArgs,
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str], bool],
    console_width: int,
) -> tuple[Layout, int]:
    """Build a single-column stats all layout with vertically stacked sections."""
    exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled = display_config
    panel_content_width = _resolve_single_column_panel_content_width(console_width)
    task_display_config = _TaskDisplayConfig(
        color_enabled=color_enabled,
        done_keys=done_keys,
        todo_keys=todo_keys,
        line_width=panel_content_width,
    )

    summary_body = format_tasks_summary(
        result,
        (date_from, date_until, done_keys, todo_keys, color_enabled),
        panel_content_width,
    ).lstrip("\n")
    tasks_body = _format_tasks_body(nodes, args.max_results, task_display_config)

    def order_by_total(item: tuple[str, Tag]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total_tasks

    category_name = CATEGORY_NAMES[args.use]
    sections: list[tuple[str, str]] = [
        ("SUMMARY", summary_body.rstrip("\n") or "No results"),
        ("TASKS", tasks_body.rstrip("\n") or "No results"),
    ]

    if args.max_tags != 0:
        tags_body_raw = format_tags_section(
            category_name,
            result.tags,
            (
                args.max_results,
                args.max_relations,
                panel_content_width,
                date_from,
                date_until,
                result.timerange,
                args.max_tags,
                exclude_set,
                color_enabled,
            ),
            order_by_total,
            indent="",
        )
        tags_body = _dedent_section_body(tags_body_raw, drop_title=args.use == "tags")
        sections.append(("TAGS", tags_body.rstrip("\n") or "No results"))

    if args.max_groups != 0:
        groups_body = _format_groups_body(
            result.tag_groups,
            exclude_set,
            args.min_group_size,
            args.max_groups,
            _GroupsDisplayConfig(
                plot_width=panel_content_width,
                date_from=date_from,
                date_until=date_until,
                global_timerange=result.timerange,
                color_enabled=color_enabled,
            ),
        )
        sections.append(("GROUPS", groups_body.rstrip("\n") or "No results"))

    root = Layout(name="root")
    section_heights = [_line_count(body) + 2 for _, body in sections]
    section_layouts = [
        Layout(
            Panel(
                _panel_body(body, color_enabled),
                title=title,
                expand=True,
                height=height,
            ),
            size=height,
        )
        for (title, body), height in zip(sections, section_heights, strict=True)
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
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str], bool],
) -> tuple[Layout, int]:
    """Build a two-column stats all layout using Rich Layout and Panels."""
    if console.width < _TWO_COLUMN_MIN_WIDTH:
        return _render_single_column_stats_all_layout(
            result, nodes, args, display_config, console.width
        )

    exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled = display_config

    panel_content_width = _resolve_two_column_panel_content_width(console.width)
    task_display_config = _TaskDisplayConfig(
        color_enabled=color_enabled,
        done_keys=done_keys,
        todo_keys=todo_keys,
        line_width=panel_content_width,
    )

    summary_body = format_tasks_summary(
        result,
        (date_from, date_until, done_keys, todo_keys, color_enabled),
        panel_content_width,
    ).lstrip("\n")

    tasks_body = _format_tasks_body(nodes, args.max_results, task_display_config)

    def order_by_total(item: tuple[str, Tag]) -> int:
        """Sort by total count (descending)."""
        return -item[1].total_tasks

    category_name = CATEGORY_NAMES[args.use]
    top_panel_height = max(_line_count(summary_body), _line_count(tasks_body)) + 2

    top_layout = Layout(name="top")
    top_layout.size = top_panel_height
    top_layout.split_row(
        Layout(
            Panel(
                _panel_body(summary_body.rstrip("\n") or "No results", color_enabled),
                title="SUMMARY",
                expand=True,
                height=top_panel_height,
            ),
            ratio=1,
        ),
        Layout(
            Panel(
                _panel_body(tasks_body.rstrip("\n") or "No results", color_enabled),
                title="TASKS",
                expand=True,
                height=top_panel_height,
            ),
            ratio=1,
        ),
    )

    tags_panel: Panel | None = None
    groups_panel: Panel | None = None
    tags_panel_height = 0
    groups_panel_height = 0

    if args.max_tags != 0:
        tags_body_raw = format_tags_section(
            category_name,
            result.tags,
            (
                args.max_results,
                args.max_relations,
                panel_content_width,
                date_from,
                date_until,
                result.timerange,
                args.max_tags,
                exclude_set,
                color_enabled,
            ),
            order_by_total,
            indent="",
        )
        tags_body = _dedent_section_body(tags_body_raw, drop_title=args.use == "tags")
        tags_panel_height = _line_count(tags_body) + 2
        tags_panel = Panel(
            _panel_body(tags_body.rstrip("\n") or "No results", color_enabled),
            title="TAGS",
            expand=True,
            height=tags_panel_height,
        )

    if args.max_groups != 0:
        groups_body = _format_groups_body(
            result.tag_groups,
            exclude_set,
            args.min_group_size,
            args.max_groups,
            _GroupsDisplayConfig(
                plot_width=panel_content_width,
                date_from=date_from,
                date_until=date_until,
                global_timerange=result.timerange,
                color_enabled=color_enabled,
            ),
        )
        groups_panel_height = _line_count(groups_body) + 2
        groups_panel = Panel(
            _panel_body(groups_body.rstrip("\n") or "No results", color_enabled),
            title="GROUPS",
            expand=True,
            height=groups_panel_height,
        )

    if tags_panel is None and groups_panel is None:
        root = Layout(name="root")
        root.size = top_panel_height
        root.update(top_layout)
        return root, top_panel_height

    bottom_layout = Layout(name="bottom")
    bottom_layout.size = max(tags_panel_height, groups_panel_height)
    bottom_layout.split_row(
        Layout(tags_panel or "", ratio=1),
        Layout(groups_panel or "", ratio=1),
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
    """Return groups body without section header and without content indentation."""
    if max_groups == 0:
        return ""

    groups_output = format_groups_section(
        groups,
        exclude_set,
        (
            min_group_size,
            config.plot_width,
            config.date_from,
            config.date_until,
            config.global_timerange,
            config.color_enabled,
        ),
        max_groups,
        indent="",
    )
    body = _dedent_section_body(groups_output, drop_title=True)
    return body or "No results\n"


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
                (exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled),
            )

    if not nodes:
        console.print("No results", markup=False)
        return
    if layout is None:
        console.print("No results", markup=False)
        return

    render_console = Console(
        no_color=not color_enabled,
        force_terminal=color_enabled,
        width=console.width,
        height=max(layout_height, 1),
        record=True,
        file=StringIO(),
    )
    render_console.print(layout)
    rendered_output = render_console.export_text(styles=color_enabled)
    print_output(console, rendered_output, color_enabled, end="")


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
        max_results: int = typer.Option(
            10,
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
