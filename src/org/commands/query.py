"""Query command for jq-style data queries."""

from __future__ import annotations

from dataclasses import dataclass

import click
import orgparse
import typer
from orgparse.date import OrgDate
from orgparse.node import OrgRootNode
from rich.console import Console
from rich.syntax import Syntax

from org import config as config_module
from org.cli_common import load_root_data
from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)
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
    color_flag: bool | None
    max_results: int
    offset: int


def _is_org_object(value: object) -> bool:
    """Return whether value is an org node or org date object."""
    return isinstance(value, orgparse.node.OrgNode | OrgRootNode | OrgDate)


def _format_org_block(value: object) -> str:
    """Build org-formatted text block for one value."""
    if isinstance(value, orgparse.node.OrgNode | OrgRootNode):
        filename = value.env.filename if value.env.filename else "unknown"
        node_text = str(value).rstrip()
        return f"# {filename}\n{node_text}" if node_text else f"# {filename}"
    if isinstance(value, OrgDate) and not bool(value):
        return "none"
    return str(value)


def _flatten_result_stream(results: list[object]) -> list[object]:
    """Flatten top-level collection result into output stream."""
    if len(results) == 1 and isinstance(results[0], (list, tuple, set)):
        return list(results[0])
    return results


def _render_org_values(values: list[object], console: Console) -> None:
    """Render org values using org-mode syntax highlighting."""
    for idx, value in enumerate(values):
        if idx > 0:
            console.print()
        console.print(
            Syntax(_format_org_block(value), "org", line_numbers=False, word_wrap=False),
        )


def _format_query_value(value: object) -> str:
    """Format one query result value for output."""
    if isinstance(value, orgparse.node.OrgNode):
        return str(value).rstrip()
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def run_query(args: QueryArgs) -> None:
    """Run the query command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")

    try:
        compiled_query = compile_query_text(args.query)
    except QueryParseError as exc:
        raise click.UsageError(str(exc)) from exc

    with processing_status(console, color_enabled):
        roots, todo_keys, done_keys = load_root_data(args)

    context = EvalContext(
        {
            "offset": args.offset,
            "limit": args.max_results,
            "todo_keys": todo_keys,
            "done_keys": done_keys,
        }
    )
    try:
        stream_nodes = Stream([roots])
        results = compiled_query(stream_nodes, context)
    except QueryRuntimeError as exc:
        raise click.UsageError(str(exc)) from exc

    output_values = _flatten_result_stream(results)
    if not output_values:
        console.print("No results", markup=False)
        return

    if all(_is_org_object(value) for value in output_values):
        _render_org_values(output_values, console)
        return

    lines = [_format_query_value(value) for value in output_values]

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
            color_flag=color_flag,
            max_results=max_results,
            offset=offset,
        )
        config_module.apply_config_defaults(args)
        run_query(args)
