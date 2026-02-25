"""Tasks list command."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import orgparse
import typer
from rich.console import Console
from rich.syntax import Syntax

from org import config as config_module
from org.cli_common import load_and_process_data
from org.tui import (
    TaskLineConfig,
    build_console,
    format_task_line,
    lines_to_text,
    print_output,
    processing_status,
    setup_output,
)


@dataclass
class ListArgs:
    """Arguments for the tasks list command."""

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
    details: bool
    offset: int
    order_by: str | list[str] | tuple[str, ...]
    with_numeric_gamify_exp: bool
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    buckets: int


def format_short_task_list(
    nodes: list[orgparse.node.OrgNode],
    done_keys: list[str],
    todo_keys: list[str],
    color_enabled: bool,
    buckets: int,
) -> str:
    """Return formatted short list of tasks."""
    lines = [
        format_task_line(
            node,
            TaskLineConfig(
                color_enabled=color_enabled,
                done_keys=done_keys,
                todo_keys=todo_keys,
                buckets=buckets,
            ),
        )
        for node in nodes
    ]
    return lines_to_text(lines)


def render_detailed_task_list(
    nodes: list[orgparse.node.OrgNode],
    console: Console,
) -> None:
    """Render detailed list of tasks with syntax highlighting."""
    for idx, node in enumerate(nodes):
        if idx > 0:
            console.print()
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        node_text = str(node).rstrip()
        org_block = f"# {filename}\n{node_text}" if node_text else f"# {filename}"
        console.print(Syntax(org_block, "org", line_numbers=False, word_wrap=False))


def run_tasks_list(args: ListArgs) -> None:
    """Run the tasks list command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results <= 0:
        console.print("No results", markup=False)
        return
    with processing_status(console, color_enabled):
        nodes, todo_keys, done_keys = load_and_process_data(args)
        if not nodes:
            display_nodes = []
            output = None
        elif args.details:
            display_nodes = nodes
            output = None
        else:
            display_nodes = nodes
            output = format_short_task_list(
                display_nodes, done_keys, todo_keys, color_enabled, args.buckets
            )

    if not nodes or not display_nodes:
        console.print("No results", markup=False)
        return

    if args.details:
        render_detailed_task_list(display_nodes, console)
        return

    if output:
        print_output(console, output, color_enabled, end="")
    else:
        console.print("No results", markup=False)


def register(app: typer.Typer) -> None:
    """Register the tasks list command."""

    @app.command("list")
    def tasks_list(  # noqa: PLR0913
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
        offset: int = typer.Option(
            0,
            "--offset",
            metavar="N",
            help="Number of results to skip before displaying",
        ),
        details: bool = typer.Option(
            False,
            "--details",
            help="Show full org node details",
        ),
        order_by: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--order-by",
            metavar="ORDER",
            help=(
                "Order tasks by: file-order, file-order-reverse, level, timestamp-asc, "
                "timestamp-desc, gamify-exp-asc, gamify-exp-desc"
            ),
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
            help="Number of time buckets for timeline charts and tag alignment column",
        ),
    ) -> None:
        """List tasks matching filters."""
        args = ListArgs(
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
            details=details,
            offset=offset,
            order_by=order_by if order_by is not None else "timestamp-desc",
            with_numeric_gamify_exp=with_numeric_gamify_exp,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            buckets=buckets,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks list")
        config_module.log_command_arguments(args, "tasks list")
        run_tasks_list(args)
