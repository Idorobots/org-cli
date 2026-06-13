"""Query building and execution helpers for command pipelines."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

import click

import org.config.app
from org.logic.time import parse_date_argument
from org.logic.validation import parse_property_filter
from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)


if TYPE_CHECKING:
    from org.query_language.compiler import CompiledQuery


logger = logging.getLogger("org")

ErrorBuilder = Callable[[str], Exception]

FILTER_OPTIONS_WITH_VALUE = {
    "--filter-priority",
    "--filter-level",
    "--filter-repeats-above",
    "--filter-repeats-below",
    "--filter-date-from",
    "--filter-date-until",
    "--filter-property",
    "--filter-tag",
    "--filter-heading",
    "--filter-body",
}

FILTER_OPTIONS_FLAGS = {
    "--filter-completed",
    "--filter-not-completed",
}

WITH_OPTIONS_FLAGS = {
    "--with-tags-as-category",
}

ORDER_BY_OPTION_TO_VALUE = {
    "--order-by-priority": "priority",
    "--order-by-level": "level",
    "--order-by-file-order": "file-order",
    "--order-by-file-order-reversed": "file-order-reversed",
    "--order-by-timestamp-asc": "timestamp-asc",
    "--order-by-timestamp-desc": "timestamp-desc",
}

ORDER_BY_DEST_TO_VALUE = {
    "order_by_priority": "priority",
    "order_by_level": "level",
    "order_by_file_order": "file-order",
    "order_by_file_order_reversed": "file-order-reversed",
    "order_by_timestamp_asc": "timestamp-asc",
    "order_by_timestamp_desc": "timestamp-desc",
}


class FilterArgs(Protocol):
    """Protocol for filter-related CLI arguments."""

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


class WithArgs(Protocol):
    """Protocol for built-in enrichment CLI arguments."""

    with_tags_as_category: bool


class QueryBuildArgs(FilterArgs, WithArgs, Protocol):
    """Protocol for arguments used to build query pipelines."""


@dataclass(frozen=True)
class CustomStageInvocation:
    """One custom switch occurrence parsed from CLI arguments."""

    name: str
    query: str
    arg_value: object


def _extract_option_token(token: str) -> str:
    """Return option token without inline assignment suffix."""
    if token.startswith("--") and "=" in token:
        return token.split("=", 1)[0]
    return token


def _custom_option_name(option: str, prefix: str) -> str | None:
    """Extract custom option name after a known prefix."""
    option_prefix = f"--{prefix}-"
    if not option.startswith(option_prefix):
        return None
    return option[len(option_prefix) :]


def _query_uses_arg(query: str) -> bool:
    """Return True when query contains the `$arg` variable."""
    return bool(re.search(r"\$arg\b", query))


def _resolve_custom_option(option: str) -> tuple[str, bool] | None:
    """Resolve configured custom option to (query, requires_arg)."""
    filter_name = _custom_option_name(option, "filter")
    if filter_name is not None:
        query = org.config.app.CONFIG_CUSTOM_FILTERS.get(filter_name)
        if query is not None:
            return (query, _query_uses_arg(query))

    order_name = _custom_option_name(option, "order-by")
    if order_name is not None:
        query = org.config.app.CONFIG_CUSTOM_ORDER_BY.get(order_name)
        if query is not None:
            return (query, _query_uses_arg(query))

    with_name = _custom_option_name(option, "with")
    if with_name is not None:
        query = org.config.app.CONFIG_CUSTOM_WITH.get(with_name)
        if query is not None:
            return (query, _query_uses_arg(query))

    return None


def _required_custom_arg_error(option: str) -> click.BadParameter:
    """Return the standard required custom argument error."""
    return click.BadParameter(f"{option} requires exactly one argument")


def normalize_cli_files_for_custom_switches(files: list[str] | None) -> list[str] | None:
    """Remove configured custom switch tokens from FILE argument values."""
    if files is None:
        return None

    normalized: list[str] = []
    index = 0
    while index < len(files):
        token = files[index]
        option = _extract_option_token(token)
        custom_option = _resolve_custom_option(option)
        if custom_option is None:
            normalized.append(token)
            index += 1
            continue

        _, requires_arg = custom_option

        if token.startswith(f"{option}="):
            index += 1
            continue

        if requires_arg:
            next_index = index + 1
            if next_index >= len(files):
                raise _required_custom_arg_error(option)

            next_token = files[next_index]
            if next_token.startswith("-"):
                raise _required_custom_arg_error(option)
            index += 2
            continue

        index += 1

    return normalized


def _consume_custom_optional_arg(
    argv: list[str],
    index: int,
    option: str,
    requires_arg: bool,
) -> tuple[str | None, int]:
    """Consume custom argument token for one custom switch occurrence."""
    if not requires_arg:
        return (None, index)

    next_index = index + 1
    if next_index >= len(argv):
        raise _required_custom_arg_error(option)

    next_token = argv[next_index]
    if next_token.startswith("-"):
        raise _required_custom_arg_error(option)

    return (next_token, next_index)


def _coerce_custom_arg_value(value: str | None) -> object:
    """Parse optional custom argument into runtime query value."""
    if value is None:
        return None

    lowered = value.lower()
    value_map: dict[str, object] = {
        "null": None,
        "true": True,
        "false": False,
    }
    if lowered in value_map:
        return value_map[lowered]

    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _build_custom_invocation(
    *,
    name: str,
    query: str,
    raw_arg: str | None,
) -> CustomStageInvocation:
    """Build one parsed custom invocation with typed context binding."""
    return CustomStageInvocation(
        name=name,
        query=query,
        arg_value=_coerce_custom_arg_value(raw_arg),
    )


def _custom_stage(query: str, arg_value: object) -> str:
    """Build one custom query stage preserving input item stream values."""
    return f"let {_query_literal(arg_value)} as $arg in ({query})"


def _query_literal(value: object) -> str:
    """Render a Python value as a query-language literal."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value)


def validate_custom_switches(argv: list[str], include_builtin_ordering: bool) -> None:
    """Validate prefixed custom switches against configured/built-in options."""
    builtin_order_options = set(ORDER_BY_OPTION_TO_VALUE) if include_builtin_ordering else set()
    allowed_filter_options = FILTER_OPTIONS_WITH_VALUE.union(FILTER_OPTIONS_FLAGS).union(
        {f"--filter-{name}" for name in org.config.app.CONFIG_CUSTOM_FILTERS},
    )
    allowed_order_options = builtin_order_options.union(
        {f"--order-by-{name}" for name in org.config.app.CONFIG_CUSTOM_ORDER_BY},
    )
    allowed_with_options = WITH_OPTIONS_FLAGS.union(
        {f"--with-{name}" for name in org.config.app.CONFIG_CUSTOM_WITH},
    )

    for index, token in enumerate(argv):
        option = _extract_option_token(token)
        if option.startswith("--filter-") and option not in allowed_filter_options:
            raise click.NoSuchOption(option)
        if option.startswith("--order-by-") and option not in allowed_order_options:
            raise click.NoSuchOption(option)
        if option.startswith("--with-") and option not in allowed_with_options:
            raise click.NoSuchOption(option)

        custom_option = _resolve_custom_option(option)
        if custom_option is None:
            continue

        _, requires_arg = custom_option
        if not requires_arg or token.startswith(f"{option}="):
            continue

        next_index = index + 1
        if next_index >= len(argv):
            raise _required_custom_arg_error(option)

        next_token = argv[next_index]
        if next_token.startswith("-"):
            raise _required_custom_arg_error(option)


def parse_filter_entries_from_argv(argv: list[str]) -> list[str | CustomStageInvocation]:
    """Parse built-in and custom filter switch occurrences in argv order."""
    entries: list[str | CustomStageInvocation] = []
    index = 0
    builtins = FILTER_OPTIONS_WITH_VALUE.union(FILTER_OPTIONS_FLAGS)
    while index < len(argv):
        token = argv[index]
        option = _extract_option_token(token)

        if option in FILTER_OPTIONS_WITH_VALUE or option in FILTER_OPTIONS_FLAGS:
            entries.append(option)
            index += 1
            continue

        name = _custom_option_name(option, "filter")
        if name is None or name not in org.config.app.CONFIG_CUSTOM_FILTERS or option in builtins:
            index += 1
            continue

        query = org.config.app.CONFIG_CUSTOM_FILTERS[name]
        requires_arg = _query_uses_arg(query)
        if token.startswith(f"{option}="):
            entries.append(
                _build_custom_invocation(name=name, query=query, raw_arg=token.split("=", 1)[1]),
            )
            index += 1
            continue

        custom_arg, consumed_index = _consume_custom_optional_arg(
            argv,
            index,
            option,
            requires_arg,
        )
        entries.append(_build_custom_invocation(name=name, query=query, raw_arg=custom_arg))
        index = consumed_index + 1

    return entries


def parse_order_entries_from_argv(
    argv: list[str],
    include_builtin_ordering: bool,
) -> list[str | CustomStageInvocation]:
    """Parse built-in and custom ordering switch occurrences in argv order."""
    entries: list[str | CustomStageInvocation] = []
    index = 0
    builtin_options = set(ORDER_BY_OPTION_TO_VALUE) if include_builtin_ordering else set()
    while index < len(argv):
        token = argv[index]
        option = _extract_option_token(token)

        builtin_value = ORDER_BY_OPTION_TO_VALUE.get(option)
        if builtin_value is not None and include_builtin_ordering:
            entries.append(builtin_value)
            index += 1
            continue

        name = _custom_option_name(option, "order-by")
        if (
            name is None
            or name not in org.config.app.CONFIG_CUSTOM_ORDER_BY
            or option in builtin_options
        ):
            index += 1
            continue

        query = org.config.app.CONFIG_CUSTOM_ORDER_BY[name]
        requires_arg = _query_uses_arg(query)
        if token.startswith(f"{option}="):
            entries.append(
                _build_custom_invocation(name=name, query=query, raw_arg=token.split("=", 1)[1]),
            )
            index += 1
            continue

        custom_arg, consumed_index = _consume_custom_optional_arg(
            argv,
            index,
            option,
            requires_arg,
        )
        entries.append(_build_custom_invocation(name=name, query=query, raw_arg=custom_arg))
        index = consumed_index + 1

    return entries


def parse_with_entries_from_argv(argv: list[str]) -> list[str | CustomStageInvocation]:
    """Parse built-in and custom enrichment switch occurrences in argv order."""
    entries: list[str | CustomStageInvocation] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        option = _extract_option_token(token)
        if option in WITH_OPTIONS_FLAGS:
            entries.append(option)
            index += 1
            continue

        name = _custom_option_name(option, "with")
        if name is None or name not in org.config.app.CONFIG_CUSTOM_WITH:
            index += 1
            continue

        query = org.config.app.CONFIG_CUSTOM_WITH[name]
        requires_arg = _query_uses_arg(query)
        if token.startswith(f"{option}="):
            entries.append(
                _build_custom_invocation(name=name, query=query, raw_arg=token.split("=", 1)[1]),
            )
            index += 1
            continue

        custom_arg, consumed_index = _consume_custom_optional_arg(
            argv,
            index,
            option,
            requires_arg,
        )
        entries.append(_build_custom_invocation(name=name, query=query, raw_arg=custom_arg))
        index = consumed_index + 1

    return entries


def extend_with_entries_with_defaults(
    with_entries: list[str | CustomStageInvocation],
    args: WithArgs,
) -> list[str | CustomStageInvocation]:
    """Extend with-entry order to include config-provided built-in enrichments."""
    expected_counts = {"--with-tags-as-category": 1 if args.with_tags_as_category else 0}
    full_entries = list(with_entries)
    for option_name, expected in expected_counts.items():
        existing = sum(1 for entry in full_entries if entry == option_name)
        missing = expected - existing
        if missing > 0:
            full_entries.extend([option_name] * missing)
    return full_entries


def extend_filter_order_with_defaults(
    filter_order: list[str | CustomStageInvocation],
    args: FilterArgs,
) -> list[str | CustomStageInvocation]:
    """Extend filter order to include config-provided filters."""
    expected_counts = {
        "--filter-priority": 1 if args.filter_priority is not None else 0,
        "--filter-level": 1 if args.filter_level is not None else 0,
        "--filter-repeats-above": 1 if args.filter_repeats_above is not None else 0,
        "--filter-repeats-below": 1 if args.filter_repeats_below is not None else 0,
        "--filter-date-from": 1 if args.filter_date_from is not None else 0,
        "--filter-date-until": 1 if args.filter_date_until is not None else 0,
        "--filter-property": len(args.filter_properties) if args.filter_properties else 0,
        "--filter-tag": len(args.filter_tags) if args.filter_tags else 0,
        "--filter-heading": len(args.filter_headings) if args.filter_headings else 0,
        "--filter-body": len(args.filter_bodies) if args.filter_bodies else 0,
        "--filter-completed": 1 if args.filter_completed else 0,
        "--filter-not-completed": 1 if args.filter_not_completed else 0,
    }

    full_order = list(filter_order)
    for arg_name, expected in expected_counts.items():
        existing = sum(1 for value in full_order if value == arg_name)
        missing = expected - existing
        if missing > 0:
            full_order.extend([arg_name] * missing)
    return full_order


def _quote_string(value: str) -> str:
    """Quote a value as query-language string literal."""
    return json.dumps(value)


def _timestamp_source_literal(value: str, arg_name: str) -> str:
    """Quote one parsed date argument as org timestamp source."""
    parsed = parse_date_argument(value, arg_name).replace(second=0, microsecond=0)
    return _quote_string(f"<{parsed:%Y-%m-%d %a %H:%M}>")


def _simple_filter_stage(arg_name: str, args: FilterArgs) -> str | None:
    """Build query stage for non-indexed filter options."""
    stage: str | None = None
    if arg_name == "--filter-priority" and args.filter_priority is not None:
        stage = f"select(.priority == {_quote_string(args.filter_priority)})"
    elif arg_name == "--filter-level" and args.filter_level is not None:
        stage = f"select(.level == {args.filter_level})"
    elif arg_name == "--filter-repeats-above" and args.filter_repeats_above is not None:
        stage = f"select(.repeats | length > {args.filter_repeats_above})"
    elif arg_name == "--filter-repeats-below" and args.filter_repeats_below is not None:
        stage = f"select(.repeats | length < {args.filter_repeats_below})"
    elif arg_name == "--filter-date-from" and args.filter_date_from is not None:
        stage = (
            "select(.repeats + .deadline + .closed + .scheduled "
            f"| max >= timestamp({_timestamp_source_literal(args.filter_date_from, arg_name)}))"
        )
    elif arg_name == "--filter-date-until" and args.filter_date_until is not None:
        stage = (
            "select(.repeats + .deadline + .closed + .scheduled "
            f"| max <= timestamp({_timestamp_source_literal(args.filter_date_until, arg_name)}))"
        )
    elif arg_name == "--filter-completed" and args.filter_completed:
        stage = (
            "select(if .repeats | length > 0"
            " then .repeats | map(.is_completed) + [.is_completed] | any"
            " else .is_completed)"
            " | .repeats = [.repeats[] | select(.is_completed)]; . "
        )
    elif arg_name == "--filter-not-completed" and args.filter_not_completed:
        stage = (
            "select(if .repeats | length > 0"
            " then not(.repeats | map(.is_completed) + [.is_completed] | any)"
            " else not(.is_completed))"
            " | .repeats = [.repeats[] | select(not(.is_completed))]; . "
        )
    return stage


def _indexed_filter_stage(
    arg_name: str,
    args: FilterArgs,
    index_trackers: dict[str, int],
) -> str | None:
    """Build query stage for indexed multi-value filter options."""
    if (
        arg_name == "--filter-property"
        and args.filter_properties
        and index_trackers["property"] < len(args.filter_properties)
    ):
        property_name, property_value = parse_property_filter(
            args.filter_properties[index_trackers["property"]],
        )
        index_trackers["property"] += 1
        return (
            f"select(.properties[{_quote_string(property_name)}] == "
            f"{_quote_string(property_value)})"
        )

    if (
        arg_name == "--filter-tag"
        and args.filter_tags
        and index_trackers["tag"] < len(args.filter_tags)
    ):
        pattern = args.filter_tags[index_trackers["tag"]]
        index_trackers["tag"] += 1
        return f"select(.tags[] matches {_quote_string(pattern)})"

    if (
        arg_name == "--filter-heading"
        and args.filter_headings
        and index_trackers["heading"] < len(args.filter_headings)
    ):
        pattern = args.filter_headings[index_trackers["heading"]]
        index_trackers["heading"] += 1
        return f"select(.title_text matches {_quote_string(pattern)})"

    if (
        arg_name == "--filter-body"
        and args.filter_bodies
        and index_trackers["body"] < len(args.filter_bodies)
    ):
        pattern = f"(?m){args.filter_bodies[index_trackers['body']]}"
        index_trackers["body"] += 1
        return f"select(.body_text matches {_quote_string(pattern)})"

    return None


def _filter_stage(arg_name: str, args: FilterArgs, index_trackers: dict[str, int]) -> str | None:
    """Build one query stage for a filter option occurrence."""
    simple_stage = _simple_filter_stage(arg_name, args)
    if simple_stage is not None:
        return simple_stage
    return _indexed_filter_stage(arg_name, args, index_trackers)


def build_filter_stages(
    args: FilterArgs,
    filter_order: list[str | CustomStageInvocation],
) -> list[str]:
    """Build query stages for filter pipeline."""
    filter_stages: list[str] = []
    index_trackers = {"property": 0, "tag": 0, "heading": 0, "body": 0}
    for entry in filter_order:
        if isinstance(entry, CustomStageInvocation):
            filter_stages.append(_custom_stage(entry.query, entry.arg_value))
            continue
        stage = _filter_stage(entry, args, index_trackers)
        if stage is not None:
            filter_stages.append(stage)
    return filter_stages


def extend_order_values_with_defaults(order_values: list[str], args: object) -> list[str]:
    """Append config-provided orderings not present in argv order."""
    expected_counts: dict[str, int] = dict.fromkeys(ORDER_BY_DEST_TO_VALUE.values(), 0)
    for dest_name, value in ORDER_BY_DEST_TO_VALUE.items():
        count = getattr(args, dest_name, 0)
        if isinstance(count, bool):
            expected_counts[value] += int(count)
        elif isinstance(count, int) and count > 0:
            expected_counts[value] += count

    full_order = list(order_values)
    for value, expected in expected_counts.items():
        existing = full_order.count(value)
        missing = expected - existing
        if missing > 0:
            full_order.extend([value] * missing)
    return full_order


def _builtin_order_stages(value: str) -> list[str]:
    """Build query stages for one built-in ordering value."""
    timestamp_key_expr = ".repeats + .deadline + .closed + .scheduled | max"
    order_stages: dict[str, list[str]] = {
        "file-order": ["."],
        "file-order-reversed": ["reverse"],
        "priority": ["sort_by(.priority)"],
        "level": ["sort_by(.level)"],
        "timestamp-asc": [
            f"sort_by({timestamp_key_expr})",
            "reverse",
            f"sort_by(({timestamp_key_expr}) != null)",
        ],
        "timestamp-desc": [f"sort_by({timestamp_key_expr})"],
    }
    return order_stages.get(value, [])


def build_order_stages(args: object, argv: list[str], include_builtin_ordering: bool) -> list[str]:
    """Build query stages for ordering pipeline."""
    order_entries = parse_order_entries_from_argv(argv, include_builtin_ordering)
    order_values: list[str | CustomStageInvocation]
    if include_builtin_ordering:
        builtin_order_values = [entry for entry in order_entries if isinstance(entry, str)]
        expected_builtins = extend_order_values_with_defaults(builtin_order_values, args)
        remaining_builtin_counts: dict[str, int] = {}
        for value in builtin_order_values:
            remaining_builtin_counts[value] = remaining_builtin_counts.get(value, 0) + 1

        missing_builtins: list[str] = []
        for value in expected_builtins:
            remaining = remaining_builtin_counts.get(value, 0)
            if remaining > 0:
                remaining_builtin_counts[value] = remaining - 1
                continue
            missing_builtins.append(value)

        order_values = [*order_entries, *missing_builtins]
        if not order_values:
            order_values = ["timestamp-desc"]
    else:
        order_values = list(order_entries)

    order_stages: list[str] = []
    for order_value in order_values:
        if isinstance(order_value, CustomStageInvocation):
            order_stages.append(_custom_stage(order_value.query, order_value.arg_value))
            continue
        order_stages.extend(_builtin_order_stages(order_value))
    return order_stages


def build_with_stages(args: WithArgs, argv: list[str]) -> list[str]:
    """Build query stages for built-in and custom enrichment pipeline."""
    entries = parse_with_entries_from_argv(argv)
    entries = extend_with_entries_with_defaults(entries, args)
    stages: list[str] = []
    for entry in entries:
        if isinstance(entry, CustomStageInvocation):
            stages.append(_custom_stage(entry.query, entry.arg_value))
            continue
        if entry == "--with-tags-as-category" and args.with_tags_as_category:
            stages.append("(if .tags | length > 0 then .heading_category = .tags[0] else null); .")
    return stages


def collect_custom_context_vars(
    argv: list[str],
    files: list[str] | None,
    include_builtin_ordering: bool,
) -> dict[str, object]:
    """Collect custom switch argument values for query evaluation context."""
    del argv, files, include_builtin_ordering
    return {}


def build_query_text(
    args: QueryBuildArgs,
    argv: list[str],
    include_ordering: bool,
    include_slice: bool,
) -> str:
    """Build query text for the configured filter/ordering pipeline."""
    validate_custom_switches(argv, include_ordering)

    filter_order = extend_filter_order_with_defaults(parse_filter_entries_from_argv(argv), args)
    filter_stages = build_filter_stages(args, filter_order)
    with_stages = build_with_stages(args, argv)
    stages = [*with_stages, *filter_stages]
    stages.extend(build_order_stages(args, argv, include_builtin_ordering=include_ordering))

    pipeline_body = " | ".join(stages)
    base_query = f"[ .[] | {pipeline_body} ]" if pipeline_body else "[ .[] ]"
    return f"{base_query}[$offset:($offset + $limit)]" if include_slice else base_query


def build_query(
    args: QueryBuildArgs,
    argv: list[str],
    include_ordering: bool,
    include_slice: bool,
) -> CompiledQuery:
    """Compile query for configured filter/ordering pipeline."""
    query_text = build_query_text(args, argv, include_ordering, include_slice)
    logger.info("Query: %s", query_text)
    return compile_query_text(query_text)


def compile_query_or_raise(query_text: str, error_builder: ErrorBuilder) -> CompiledQuery:
    """Compile query text and convert parse failures to caller-specific errors."""
    try:
        return compile_query_text(query_text)
    except QueryParseError as exc:
        raise error_builder(str(exc)) from exc


def compile_filter_order_query(filter_query: str, order_by: str | None) -> CompiledQuery:
    """Compile a `select(...)` query with optional sort stage."""
    base_query = f"select({filter_query})"
    if order_by is None:
        return compile_query_text(base_query)
    return compile_query_text(f"{base_query} | sort_by({order_by})")


def execute_query(
    compiled_query: CompiledQuery,
    stream_values: Sequence[object],
    context_vars: dict[str, object],
) -> list[object]:
    """Execute a compiled query over stream input values."""
    return list(compiled_query(Stream(stream_values), EvalContext(context_vars)))


def execute_query_or_raise(
    compiled_query: CompiledQuery,
    stream_values: Sequence[object],
    context_vars: dict[str, object],
    error_builder: ErrorBuilder,
) -> list[object]:
    """Execute query and convert runtime failures to caller-specific errors."""
    try:
        return execute_query(compiled_query, stream_values, context_vars)
    except QueryRuntimeError as exc:
        raise error_builder(str(exc)) from exc


def run_query_text_or_raise(
    query_text: str,
    stream_values: Sequence[object],
    context_vars: dict[str, object],
    error_builder: ErrorBuilder,
) -> list[object]:
    """Compile and execute query text with caller-specific error conversion."""
    return execute_query_or_raise(
        compile_query_or_raise(query_text, error_builder),
        stream_values,
        context_vars,
        error_builder,
    )


def flatten_query_results(results: list[object]) -> list[object]:
    """Flatten common single-list query result shape."""
    if len(results) == 1 and isinstance(results[0], list):
        return cast("list[object]", results[0])
    return list(results)
