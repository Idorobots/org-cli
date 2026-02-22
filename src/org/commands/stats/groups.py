"""Stats groups command."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import typer

from org import config as config_module
from org.analyze import (
    Group,
    TimeRange,
    compute_explicit_groups,
    compute_frequencies,
    compute_global_timerange,
    compute_groups,
    compute_per_tag_statistics,
    compute_relations,
    compute_time_ranges,
)
from org.cli_common import (
    load_and_process_data,
    resolve_exclude_set,
    resolve_group_values,
    resolve_mapping,
)
from org.tui import (
    GroupBlockConfig,
    TimelineFormatConfig,
    apply_indent,
    format_group_block,
    lines_to_text,
    setup_output,
)
from org.validation import parse_date_argument, validate_stats_arguments


@dataclass
class GroupsArgs:
    """Arguments for the stats groups command."""

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
    groups: list[str] | None
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    max_relations: int
    min_group_size: int
    max_groups: int
    buckets: int


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
        return lines_to_text(apply_indent(["No results"], indent))

    lines: list[str] = []
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
                        indent="",
                    ),
                    name_indent="",
                    stats_indent="  ",
                ),
            )
        )

    return lines_to_text(apply_indent(lines, indent))


def run_stats_groups(args: GroupsArgs) -> None:
    """Run the stats groups command."""
    color_enabled = setup_output(args)
    validate_stats_arguments(args)

    mapping = resolve_mapping(args)
    exclude_set = resolve_exclude_set(args)

    nodes, _, _ = load_and_process_data(args)

    if not nodes:
        print("No results")
        return

    global_timerange = compute_global_timerange(nodes)

    date_from = None
    date_until = None
    if args.filter_date_from is not None:
        date_from = parse_date_argument(args.filter_date_from, "--filter-date-from")
    if args.filter_date_until is not None:
        date_until = parse_date_argument(args.filter_date_until, "--filter-date-until")

    group_values = resolve_group_values(args.groups, mapping, args.use)

    if group_values is not None:
        tag_time_ranges = compute_time_ranges(nodes, mapping, args.use)
        groups = compute_explicit_groups(nodes, mapping, args.use, group_values, tag_time_ranges)
    else:
        frequencies = compute_frequencies(nodes, mapping, args.use)
        time_ranges = compute_time_ranges(nodes, mapping, args.use)
        relations = compute_relations(nodes, mapping, args.use) if args.max_relations > 0 else {}
        tags = compute_per_tag_statistics(frequencies, relations, time_ranges)
        groups = sorted(
            compute_groups(tags, args.max_relations, nodes, mapping, args.use),
            key=lambda group: len(group.tags),
            reverse=True,
        )

    output = format_group_list(
        groups,
        (
            args.max_results,
            args.buckets,
            date_from,
            date_until,
            global_timerange,
            exclude_set,
            color_enabled,
        ),
    )
    if output:
        print(output, end="")


def register(app: typer.Typer) -> None:
    """Register the stats groups command."""

    @app.command("groups")
    def stats_groups(  # noqa: PLR0913
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
        use: str = typer.Option(
            "tags",
            "--use",
            metavar="CATEGORY",
            help="Category to display: tags, heading, or body",
        ),
        groups: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--group",
            metavar="TAGS",
            help="Comma-separated list of tags to group (can specify multiple)",
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
            help="Maximum number of relations to consider per item (use 0 to omit sections)",
        ),
        buckets: int = typer.Option(
            50,
            "--buckets",
            metavar="N",
            help="Number of time buckets for timeline charts (minimum: 20)",
        ),
    ) -> None:
        """Show tag groups for selected groups or top results."""
        args = GroupsArgs(
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
            max_tags=0,
            use=use,
            groups=groups,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=max_relations,
            min_group_size=0,
            max_groups=0,
            buckets=buckets,
        )
        config_module.apply_config_defaults(args)
        run_stats_groups(args)
