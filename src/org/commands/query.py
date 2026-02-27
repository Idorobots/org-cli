"""Query command for jq-style data queries."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import click
import typer

from org import config as config_module
from org.cli_common import load_root_data
from org.output_format import (
    DEFAULT_OUTPUT_THEME,
    OutputFormat,
    OutputFormatError,
    get_query_formatter,
    print_prepared_output,
)
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
    out: str
    out_theme: str
    pandoc_args: str | None


def run_query(args: QueryArgs) -> None:
    """Run the query command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    try:
        formatter = get_query_formatter(args.out, args.pandoc_args)
    except OutputFormatError as exc:
        raise click.UsageError(str(exc)) from exc

    with processing_status(console, color_enabled):
        try:
            compiled_query = compile_query_text(args.query)
        except QueryParseError as exc:
            raise click.UsageError(str(exc)) from exc

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

        first_result = results[0] if results else None
        if len(results) == 1 and isinstance(first_result, list | tuple | set):
            output_values = list(first_result)
        else:
            output_values = list(results)

        try:
            prepared_output = formatter.prepare(
                output_values, console, color_enabled, args.out_theme
            )
        except OutputFormatError as exc:
            raise click.UsageError(str(exc)) from exc

    print_prepared_output(console, prepared_output)


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
        out: str = typer.Option(
            OutputFormat.ORG,
            "--out",
            help="Output format: org, json, or any pandoc writer format",
        ),
        out_theme: str = typer.Option(
            DEFAULT_OUTPUT_THEME,
            "--out-theme",
            help="Syntax theme for highlighted output blocks",
        ),
        pandoc_args: str | None = typer.Option(
            None,
            "--pandoc-args",
            metavar="ARGS",
            help="Additional arguments forwarded to pandoc export",
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
            out=out,
            out_theme=out_theme,
            pandoc_args=pandoc_args,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "query")
        config_module.log_command_arguments(args, "query")
        run_query(args)
