"""Stats tags command."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime

import typer

from org import config as config_module
from org.analyze import (
    Tag,
    TimeRange,
    clean,
    compute_frequencies,
    compute_global_timerange,
    compute_per_tag_statistics,
    compute_relations,
    compute_time_ranges,
)
from org.cli_common import (
    load_and_process_data,
    normalize_show_value,
    resolve_date_filters,
    resolve_exclude_set,
    resolve_mapping,
)
from org.tui import (
    TagBlockConfig,
    TimelineFormatConfig,
    apply_indent,
    build_console,
    format_tag_block,
    lines_to_text,
    print_output,
    processing_status,
    setup_output,
)
from org.validation import parse_show_values, validate_stats_arguments


@dataclass
class TagsArgs:
    """Arguments for the stats tags command."""

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
    max_results: int
    max_tags: int
    use: str
    show: str | None
    with_numeric_gamify_exp: bool
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    max_relations: int
    min_group_size: int
    max_groups: int
    buckets: int


def format_tags(
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
        return lines_to_text(apply_indent(["No results"], indent))

    lines: list[str] = []
    for idx, (name, tag) in enumerate(selected_items):
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
                        indent="",
                    ),
                    name_indent="",
                    stats_indent="  ",
                ),
            )
        )

    return lines_to_text(apply_indent(lines, indent))


def _resolve_show_values(args: TagsArgs, mapping: dict[str, str]) -> list[str] | None:
    if args.show is None:
        return None

    raw_values = parse_show_values(args.show)
    if args.use == "tags":
        return [mapping.get(value.strip(), value.strip()) for value in raw_values]

    show_values: list[str] = []
    for value in raw_values:
        normalized_value = normalize_show_value(value, mapping)
        if normalized_value:
            show_values.append(normalized_value)
    return show_values


def run_stats_tags(args: TagsArgs) -> None:
    """Run the stats tags command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    validate_stats_arguments(args)

    with processing_status(console, color_enabled):
        mapping = resolve_mapping(args)
        exclude_set = resolve_exclude_set(args)
        nodes, _, _ = load_and_process_data(args)

        if not nodes:
            output = None
        else:
            frequencies = compute_frequencies(nodes, mapping, args.use)
            time_ranges = compute_time_ranges(nodes, mapping, args.use)
            relations = (
                compute_relations(nodes, mapping, args.use) if args.max_relations > 0 else {}
            )
            tags = compute_per_tag_statistics(frequencies, relations, time_ranges)
            global_timerange = compute_global_timerange(nodes)

            date_from, date_until = resolve_date_filters(args)
            show_values = _resolve_show_values(args, mapping)

            output = format_tags(
                tags,
                show_values,
                (
                    args.max_results,
                    args.max_relations,
                    args.buckets,
                    date_from,
                    date_until,
                    global_timerange,
                    exclude_set,
                    color_enabled,
                ),
            )

    if not nodes:
        console.print("No results", markup=False)
        return
    if output:
        print_output(console, output, color_enabled, end="")


def register(app: typer.Typer) -> None:
    """Register the stats tags command."""

    @app.command("tags")
    def stats_tags(  # noqa: PLR0913
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
        max_results: int = typer.Option(
            10,
            "--max-results",
            "-n",
            metavar="N",
            help="Maximum number of results to display",
        ),
        use: str = typer.Option(
            "tags",
            "--use",
            metavar="CATEGORY",
            help="Category to display: tags, heading, or body",
        ),
        show: str | None = typer.Option(
            None,
            "--show",
            metavar="TAGS",
            help="Comma-separated list of tags to display (default: top results)",
        ),
        with_gamify_category: bool = typer.Option(
            False,
            "--with-gamify-category",
            help="Preprocess nodes to set category property based on gamify_exp value",
        ),
        with_numeric_gamify_exp: bool = typer.Option(
            False,
            "--with-numeric-gamify-exp",
            help="Normalize gamify_exp property values to strict numeric form",
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
        buckets: int = typer.Option(
            50,
            "--buckets",
            metavar="N",
            help="Number of time buckets for timeline charts (minimum: 20)",
        ),
    ) -> None:
        """Show tag stats for selected tags or top results."""
        args = TagsArgs(
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
            max_results=max_results,
            max_tags=0,
            use=use,
            show=show,
            with_numeric_gamify_exp=with_numeric_gamify_exp,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=2,
            max_groups=0,
            buckets=buckets,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "stats tags")
        config_module.log_command_arguments(args, "stats tags")
        run_stats_tags(args)
