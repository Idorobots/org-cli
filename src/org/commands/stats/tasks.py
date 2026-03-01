"""Stats tasks command."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import typer

from org import config as config_module
from org.analyze import (
    AnalysisResult,
    compute_avg_tasks_per_day,
    compute_category_histogram,
    compute_day_of_week_histogram,
    compute_global_timerange,
    compute_max_single_day,
    compute_priority_histogram,
    compute_task_state_histogram,
    compute_task_stats,
)
from org.cli_common import load_and_process_data, resolve_date_filters
from org.color import magenta
from org.histogram import RenderConfig
from org.tui import (
    HistogramSectionConfig,
    TimelineFormatConfig,
    apply_indent,
    build_console,
    format_histogram_section,
    format_timeline_lines,
    lines_to_text,
    print_output,
    processing_status,
    setup_output,
)
from org.validation import validate_stats_arguments


@dataclass
class TasksArgs:
    """Arguments for the stats tasks command."""

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
    max_results: int
    max_tags: int
    use: str
    with_numeric_gamify_exp: bool
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    max_relations: int
    min_group_size: int
    max_groups: int
    buckets: int


class TaskDisplayArgs(Protocol):
    """Protocol for display arguments used in task summary output."""

    buckets: int


def format_tasks_summary(
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
            format_timeline_lines(
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

    unique_tasks_value = magenta(str(result.unique_tasks), color_enabled)
    lines.append(f"Unique tasks: {unique_tasks_value}")

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
        format_histogram_section(
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

    priority_order = sorted(result.task_priorities.values.keys())
    lines.extend(
        format_histogram_section(
            "Task priorities:",
            result.task_priorities,
            HistogramSectionConfig(
                buckets=args.buckets,
                order=priority_order,
                render_config=RenderConfig(color_enabled=color_enabled),
                indent="",
            ),
        )
    )

    category_order = sorted(result.task_categories.values.keys())
    lines.extend(
        format_histogram_section(
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
        format_histogram_section(
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

    return lines_to_text(apply_indent(lines, indent))


def run_stats_tasks(args: TasksArgs) -> None:
    """Run the stats tasks command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    validate_stats_arguments(args)
    with processing_status(console, color_enabled):
        nodes, todo_keys, done_keys = load_and_process_data(args)

        if not nodes:
            output = None
        else:
            global_timerange = compute_global_timerange(nodes)
            total_tasks, max_repeat_count = compute_task_stats(nodes)
            unique_tasks = len(nodes)
            max_single_day = compute_max_single_day(global_timerange)
            avg_tasks_per_day = compute_avg_tasks_per_day(global_timerange, total_tasks)

            result = AnalysisResult(
                total_tasks=total_tasks,
                unique_tasks=unique_tasks,
                task_states=compute_task_state_histogram(nodes),
                task_categories=compute_category_histogram(nodes, args.category_property),
                task_priorities=compute_priority_histogram(nodes),
                task_days=compute_day_of_week_histogram(nodes),
                timerange=global_timerange,
                avg_tasks_per_day=avg_tasks_per_day,
                max_single_day_count=max_single_day,
                max_repeat_count=max_repeat_count,
                tags={},
                tag_groups=[],
            )

            date_from, date_until = resolve_date_filters(args)

            output = format_tasks_summary(
                result,
                args,
                (date_from, date_until, done_keys, todo_keys, color_enabled),
            )

    if not nodes:
        console.print("No results", markup=False)
        return
    if output:
        print_output(console, output, color_enabled, end="")


def register(app: typer.Typer) -> None:
    """Register the stats tasks command."""

    @app.command(
        "tasks",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def stats_tasks(  # noqa: PLR0913
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
        max_results: int = typer.Option(
            10,
            "--max-results",
            "-n",
            metavar="N",
            help="Maximum number of results to display",
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
        buckets: int = typer.Option(
            50,
            "--buckets",
            metavar="N",
            help="Number of time buckets for timeline charts (minimum: 20)",
        ),
    ) -> None:
        """Show overall task stats without tag sections."""
        args = TasksArgs(
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
            max_results=max_results,
            max_tags=5,
            use="tags",
            with_numeric_gamify_exp=with_numeric_gamify_exp,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            max_relations=5,
            min_group_size=2,
            max_groups=5,
            buckets=buckets,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "stats tasks")
        config_module.log_command_arguments(args, "stats tasks")
        run_stats_tasks(args)
