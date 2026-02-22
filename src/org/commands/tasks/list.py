"""Tasks list command."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import orgparse
import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from org import config as config_module
from org.cli_common import get_most_recent_timestamp, load_and_process_data
from org.filters import get_gamify_exp
from org.tui import (
    TaskLineConfig,
    build_console,
    format_task_line,
    lines_to_text,
    print_output,
    processing_status,
    setup_output,
)


@dataclass(frozen=True)
class OrderSpec:
    """Ordering specification for task lists."""

    key: Callable[[orgparse.node.OrgNode], float | int | None]
    direction: int
    label: str


def _timestamp_value(node: orgparse.node.OrgNode) -> float | None:
    timestamp = get_most_recent_timestamp(node)
    return timestamp.timestamp() if timestamp else None


def _gamify_exp_value(node: orgparse.node.OrgNode) -> int | None:
    return get_gamify_exp(node)


def _level_value(node: orgparse.node.OrgNode) -> int | None:
    level = node.level
    if level is None:
        return None
    return cast(int, level)


def _constant_value(_: orgparse.node.OrgNode) -> int:
    return 0


ORDER_SPECS: dict[str, OrderSpec] = {
    "file-order": OrderSpec(
        key=_constant_value,
        direction=1,
        label="file order",
    ),
    "file-order-reverse": OrderSpec(
        key=_constant_value,
        direction=1,
        label="file order reversed",
    ),
    "timestamp-asc": OrderSpec(
        key=_timestamp_value,
        direction=1,
        label="most recent timestamp ascending",
    ),
    "timestamp-desc": OrderSpec(
        key=_timestamp_value,
        direction=-1,
        label="most recent timestamp descending",
    ),
    "gamify-exp-asc": OrderSpec(
        key=_gamify_exp_value,
        direction=1,
        label="gamify_exp ascending",
    ),
    "gamify-exp-desc": OrderSpec(
        key=_gamify_exp_value,
        direction=-1,
        label="gamify_exp descending",
    ),
    "level": OrderSpec(
        key=_level_value,
        direction=1,
        label="level ascending",
    ),
}


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
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str


def normalize_order_by(order_by: str | list[str] | tuple[str, ...]) -> list[str]:
    """Normalize order_by values into a list."""
    if isinstance(order_by, list):
        return order_by
    if isinstance(order_by, tuple):
        return list(order_by)
    return [order_by]


def validate_order_by(order_by: list[str]) -> None:
    """Validate order_by values."""
    invalid = [value for value in order_by if value not in ORDER_SPECS]
    if not invalid:
        return

    supported = ", ".join(ORDER_SPECS)
    invalid_list = ", ".join(invalid)
    raise typer.BadParameter(f"--order-by must be one of: {supported}\nGot: {invalid_list}")


def order_nodes(
    nodes: list[orgparse.node.OrgNode],
    order_by: list[str],
) -> list[orgparse.node.OrgNode]:
    """Order nodes using the selected order criteria in sequence."""
    validate_order_by(order_by)
    ordered_nodes = list(nodes)

    for order_value in order_by:
        if order_value == "file-order":
            continue
        if order_value == "file-order-reverse":
            ordered_nodes.reverse()
            continue

        order_spec = ORDER_SPECS[order_value]
        key_fn = order_spec.key
        direction = order_spec.direction

        def sort_key(
            node: orgparse.node.OrgNode,
            key_func: Callable[[orgparse.node.OrgNode], float | int | None] = key_fn,
            direction_value: int = direction,
        ) -> tuple[int, float | int]:
            value = key_func(node)
            if value is None:
                return (1, 0)
            return (0, direction_value * value)

        ordered_nodes = sorted(ordered_nodes, key=sort_key)

    return ordered_nodes


def format_short_task_list(
    nodes: list[orgparse.node.OrgNode],
    done_keys: list[str],
    todo_keys: list[str],
    color_enabled: bool,
) -> str:
    """Return formatted short list of tasks."""
    lines = [
        format_task_line(
            node,
            TaskLineConfig(
                color_enabled=color_enabled,
                done_keys=done_keys,
                todo_keys=todo_keys,
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
        header = Text(f"# {filename}")
        header.no_wrap = True
        header.overflow = "ignore"
        console.print(header, markup=False)
        console.print(Syntax(node_text, "org", line_numbers=False, word_wrap=False))


def run_tasks_list(args: ListArgs) -> None:
    """Run the tasks list command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    order_by = normalize_order_by(args.order_by)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    with processing_status(console, color_enabled):
        nodes, todo_keys, done_keys = load_and_process_data(args)
        if not nodes or args.max_results <= 0:
            limited_nodes = []
            output = None
        else:
            ordered_nodes = order_nodes(nodes, order_by)
            offset_nodes = ordered_nodes[args.offset :]
            limited_nodes = offset_nodes[: args.max_results]
            if args.details:
                output = None
            else:
                output = format_short_task_list(limited_nodes, done_keys, todo_keys, color_enabled)

    if not nodes or not limited_nodes:
        console.print("No results", markup=False)
        return

    if args.details:
        render_detailed_task_list(limited_nodes, console)
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
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
        )
        config_module.apply_config_defaults(args)
        run_tasks_list(args)
