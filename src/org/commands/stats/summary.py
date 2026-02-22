"""Stats summary command."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import orgparse
import typer
from colorama import init as colorama_init

from org import config as config_module
from org.analyze import AnalysisResult, Tag, TimeRange, analyze, clean
from org.cli_common import (
    CATEGORY_NAMES,
    build_filter_chain,
    load_nodes,
    resolve_exclude_set,
    resolve_input_paths,
    resolve_mapping,
)
from org.color import should_use_color
from org.commands.stats.tasks import format_tasks_summary
from org.filters import preprocess_gamify_categories, preprocess_tags_as_category
from org.tui import (
    TagBlockConfig,
    TimelineFormatConfig,
    TopTasksSectionConfig,
    apply_indent,
    format_groups_section,
    format_tag_block,
    format_top_tasks_section,
    lines_to_text,
    section_header_lines,
)
from org.validation import parse_date_argument, validate_global_arguments, validate_stats_arguments


@dataclass
class SummaryArgs:
    """Arguments for the stats summary command."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_keys: str
    done_keys: str
    filter_gamify_exp_above: int | None
    filter_gamify_exp_below: int | None
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
    max_results: int
    max_tags: int
    use: str
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    max_relations: int
    min_group_size: int
    max_groups: int
    buckets: int


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


def format_stats_summary_output(
    result: AnalysisResult,
    nodes: list[orgparse.node.OrgNode],
    args: SummaryArgs,
    display_config: tuple[set[str], datetime | None, datetime | None, list[str], list[str], bool],
) -> str:
    """Return formatted output for the stats summary command."""
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
                args,
                (date_from, date_until, done_keys, todo_keys, color_enabled),
            ),
            format_top_tasks_section(
                nodes,
                TopTasksSectionConfig(
                    max_results=args.max_results,
                    color_enabled=color_enabled,
                    done_keys=done_keys,
                    todo_keys=todo_keys,
                    indent="",
                ),
            ),
            format_tags_section(
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
                indent="  ",
            ),
            format_groups_section(
                result.tag_groups,
                exclude_set,
                (
                    args.min_group_size,
                    args.buckets,
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


def run_stats(args: SummaryArgs) -> None:
    """Run the stats command."""
    color_enabled = should_use_color(args.color_flag)

    if color_enabled:
        colorama_init(autoreset=True, strip=False)

    todo_keys, done_keys = validate_global_arguments(args)
    validate_stats_arguments(args)

    mapping = resolve_mapping(args)
    exclude_set = resolve_exclude_set(args)

    filters = build_filter_chain(args, sys.argv)

    filenames = resolve_input_paths(args.files)
    nodes, todo_keys, done_keys = load_nodes(filenames, todo_keys, done_keys, [])

    if args.with_gamify_category:
        nodes = preprocess_gamify_categories(nodes, args.category_property)

    if args.with_tags_as_category:
        nodes = preprocess_tags_as_category(nodes, args.category_property)

    for filter_spec in filters:
        nodes = filter_spec.filter(nodes)

    if not nodes:
        print("No results")
        return

    result = analyze(nodes, mapping, args.use, args.max_relations, args.category_property)

    date_from = None
    date_until = None
    if args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
    if args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")

    output = format_stats_summary_output(
        result,
        nodes,
        args,
        (exclude_set, date_from, date_until, done_keys, todo_keys, color_enabled),
    )
    if output:
        print(output, end="")


def register(app: typer.Typer) -> None:
    """Register the stats summary command."""

    @app.command("summary")
    def stats_summary(  # noqa: PLR0913
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
        filter_gamify_exp_above: int | None = typer.Option(
            None,
            "--filter-gamify-exp-above",
            metavar="N",
            help="Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)",
        ),
        filter_gamify_exp_below: int | None = typer.Option(
            None,
            "--filter-gamify-exp-below",
            metavar="N",
            help="Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)",
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
        max_results: int = typer.Option(
            10,
            "--max-results",
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
        with_gamify_category: bool = typer.Option(
            False,
            "--with-gamify-category",
            help="Preprocess nodes to set category property based on gamify_exp value",
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
        buckets: int = typer.Option(
            50,
            "--buckets",
            metavar="N",
            help="Number of time buckets for timeline charts (minimum: 20)",
        ),
    ) -> None:
        """Show overall task stats."""
        args = SummaryArgs(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=None,
            exclude_inline=None,
            todo_keys=todo_keys,
            done_keys=done_keys,
            filter_gamify_exp_above=filter_gamify_exp_above,
            filter_gamify_exp_below=filter_gamify_exp_below,
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
            max_results=max_results,
            max_tags=max_tags,
            use=use,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=min_group_size,
            max_groups=max_groups,
            buckets=buckets,
        )
        config_module.apply_config_defaults(args)
        run_stats(args)
