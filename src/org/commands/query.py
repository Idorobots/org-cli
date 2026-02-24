"""Query command for jq-style data queries."""

from __future__ import annotations

from dataclasses import dataclass

import orgparse
import typer

from org import config as config_module
from org.cli_common import load_and_process_data
from org.order import normalize_order_by, order_nodes
from org.query_language import EvalContext, QueryParseError, QueryRuntimeError, compile_query_text
from org.tui import build_console, processing_status, setup_output


@dataclass
class QueryArgs:
    """Arguments for the query command."""

    query: str
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
    offset: int
    order_by: str | list[str] | tuple[str, ...] | None
    with_gamify_category: bool
    with_tags_as_category: bool
    category_property: str
    buckets: int


def _format_query_value(value: object) -> str:
    """Format one query result value for output."""
    if isinstance(value, orgparse.node.OrgNode):
        return str(value).rstrip()
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _to_output_lines(results: list[object]) -> list[str]:
    """Convert query results into printable lines."""
    if len(results) == 1 and isinstance(results[0], (list, tuple, set)):
        collection = list(results[0])
        return [_format_query_value(value) for value in collection]
    return [_format_query_value(value) for value in results]


def run_query(args: QueryArgs) -> None:
    """Run the query command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    order_by = normalize_order_by(args.order_by)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")

    try:
        compiled_query = compile_query_text(args.query)
    except QueryParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    with processing_status(console, color_enabled):
        nodes, todo_keys, done_keys = load_and_process_data(args)
        if order_by and nodes:
            nodes = order_nodes(nodes, order_by)

    context = EvalContext(
        {
            "offset": args.offset,
            "limit": args.max_results,
            "todo_keys": todo_keys,
            "done_keys": done_keys,
        }
    )
    try:
        stream_nodes: list[object] = [nodes]
        results = compiled_query(stream_nodes, context)
    except QueryRuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    lines = _to_output_lines(results)
    if not lines:
        console.print("No results", markup=False)
        return

    for line in lines:
        console.print(line, markup=False)


def register(app: typer.Typer) -> None:
    """Register the query command."""

    @app.command("query")
    def query_command(  # noqa: PLR0913
        query: str = typer.Argument(..., metavar="QUERY", help="jq-style query expression"),
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
        buckets: int = typer.Option(
            50,
            "--buckets",
            metavar="N",
            help="Number of time buckets for timeline charts and tag alignment column",
        ),
    ) -> None:
        """Query tasks using jq-style expressions."""
        args = QueryArgs(
            query=query,
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
            offset=offset,
            order_by=order_by,
            with_gamify_category=with_gamify_category,
            with_tags_as_category=with_tags_as_category,
            category_property=category_property,
            buckets=buckets,
        )
        config_module.apply_config_defaults(args)
        run_query(args)
