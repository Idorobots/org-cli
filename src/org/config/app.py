"""Configuration handling for the org CLI."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict, TypeGuard, TypeVar, cast

import typer
import yaml


COMMAND_OPTION_NAMES = {
    "date",
    "days",
    "color_flag",
    "config",
    "details",
    "done_states",
    "exclude",
    "filter_bodies",
    "filter_completed",
    "filter_date_from",
    "filter_date_until",
    "filter_priority",
    "filter_level",
    "filter_headings",
    "filter_not_completed",
    "filter_properties",
    "filter_repeats_above",
    "filter_repeats_below",
    "filter_tags",
    "mapping",
    "max_groups",
    "max_relations",
    "max_results",
    "max_tags",
    "min_group_size",
    "no_completed",
    "no_overdue",
    "no_upcoming",
    "future_repeats",
    "offset",
    "out",
    "out_theme",
    "pandoc_args",
    "order_by_file_order",
    "order_by_file_order_reversed",
    "order_by_priority",
    "order_by_level",
    "order_by_timestamp_asc",
    "order_by_timestamp_desc",
    "todo_states",
    "tags",
    "use",
    "view",
    "with_tags_as_category",
    "groups",
    "verbose",
    "width",
}


MAP: dict[str, str] = {}

TAGS: set[str] = set()

HEADING = {
    "the",
    "to",
    "a",
    "for",
    "in",
    "of",
    "and",
    "on",
    "with",
    "some",
    "out",
    "&",
    "up",
    "from",
    "an",
    "into",
    "new",
    "why",
    "do",
    "ways",
    "say",
    "it",
    "this",
    "is",
    "no",
    "not",
    "that",
    "all",
    "but",
    "be",
    "use",
    "now",
    "will",
    "i",
    "as",
    "or",
    "by",
    "did",
    "can",
    "are",
    "was",
    "more",
    "until",
    "using",
    "when",
    "only",
    "at",
    "it's",
    "have",
    "about",
    "just",
    "get",
    "didn't",
    "can't",
    "my",
    "does",
    "etc",
    "there",
    "yet",
    "nope",
    "should",
    "i'll",
    "nah",
}

DEFAULT_EXCLUDE = TAGS.union(HEADING).union(
    {
        "end",
        "logbook",
        "cancelled",
        "scheduled",
        "suspended",
        "",
    },
)

CATEGORY_NAMES = {"tags": "tags", "heading": "heading words", "body": "body words"}

T = TypeVar("T")

if TYPE_CHECKING:
    from collections.abc import Callable


def normalize_exclude_values(values: list[str]) -> set[str]:
    """Normalize exclude values to match file-based behavior."""
    return {line.strip() for line in values if line.strip()}


def resolve_verbose(verbose: bool | None) -> bool:
    """Resolve effective verbose setting from CLI flag and config defaults."""
    if verbose is None:
        return False
    return verbose


def load_exclude_list(filepath: str | None) -> set[str]:
    """Load exclude list from a file (one word per line).

    Args:
        filepath: Path to exclude list file, or None for empty set

    Returns:
        Set of excluded tags (lowercased, stripped)

    Raises:
        typer.BadParameter: If file cannot be read
    """
    if filepath is None:
        return set()

    path = Path(filepath)
    try:
        with path.open(encoding="utf-8") as f:
            return normalize_exclude_values(list(f))
    except FileNotFoundError as err:
        raise typer.BadParameter(f"Exclude list file '{filepath}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{filepath}'") from err


def load_mapping(filepath: str | None) -> dict[str, str]:
    """Load tag mapping from a JSON file.

    Args:
        filepath: Path to JSON mapping file, or None for empty dict

    Returns:
        Dictionary mapping tags to canonical forms

    Raises:
        typer.BadParameter: If file cannot be read or JSON is invalid
    """
    if filepath is None:
        return {}

    path = Path(filepath)
    try:
        with path.open(encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            raise typer.BadParameter(f"Mapping file '{filepath}' must contain a JSON object")

        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise typer.BadParameter(f"All keys and values in '{filepath}' must be strings")

    except FileNotFoundError as err:
        raise typer.BadParameter(f"Mapping file '{filepath}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{filepath}'") from err
    except json.JSONDecodeError as err:
        raise typer.BadParameter(f"Invalid JSON in '{filepath}': {err}") from err
    else:
        return mapping


def resolve_mapping(args: object) -> dict[str, str]:
    """Resolve mapping based on inline or file-based configuration."""
    mapping_inline = getattr(args, "mapping_inline", None)
    if mapping_inline is not None:
        return mapping_inline or MAP
    mapping_file = getattr(args, "mapping", None)
    return load_mapping(mapping_file) or MAP


def resolve_exclude_set(args: object) -> set[str]:
    """Resolve exclude set based on inline or file-based configuration."""
    exclude_inline = getattr(args, "exclude_inline", None)
    if exclude_inline is not None:
        return normalize_exclude_values(exclude_inline) or DEFAULT_EXCLUDE
    exclude_file = getattr(args, "exclude", None)
    return load_exclude_list(exclude_file) or DEFAULT_EXCLUDE


@dataclass(frozen=True)
class BoardColumnConfig:
    """One configured board column."""

    name: str
    filter: str
    order_by: str | None = None


@dataclass(frozen=True)
class BoardViewConfig:
    """One configured board view."""

    name: str
    columns: list[BoardColumnConfig]


@dataclass(frozen=True)
class AgendaSectionConfig:
    """One configured agenda section."""

    name: str
    filter: str
    order_by: str | None = None
    style: str = ""
    timeline: bool = False


@dataclass(frozen=True)
class AgendaViewConfig:
    """One configured agenda view."""

    name: str
    sections: list[AgendaSectionConfig]


@dataclass(frozen=True)
class NamedQueryConfig:
    """One named custom query snippet."""

    name: str
    query: str


@dataclass
class StatsConfig:
    """Structured configuration for stats-related defaults and resources."""

    exclude: str | None = None
    exclude_inline: list[str] | None = None
    mapping: str | None = None
    mapping_inline: dict[str, str] | None = None
    max_results: int | None = None
    max_tags: int | None = None
    max_relations: int | None = None
    min_group_size: int | None = None
    max_groups: int | None = None
    use: str | None = None
    tags: list[str] | None = None
    groups: list[str] | None = None


@dataclass
class TasksConfig:
    """Structured configuration for task-listing defaults."""

    max_results: int | None = None
    details: bool | None = None
    out: str | None = None
    out_theme: str | None = None
    pandoc_args: str | None = None


@dataclass
class CaptureConfig:
    """Structured configuration for capture templates."""

    templates: dict[str, dict[str, str]]


@dataclass
class AgendaConfig:
    """Structured configuration for agenda command settings."""

    views: dict[str, AgendaViewConfig]
    date: str | None = None
    days: int | None = None
    no_completed: bool | None = None
    no_overdue: bool | None = None
    no_upcoming: bool | None = None
    future_repeats: bool | None = None
    view: str | None = None
    max_results: int | None = None
    offset: int | None = None
    width: int | None = None


@dataclass
class BoardConfig:
    """Structured configuration for board command settings."""

    views: dict[str, BoardViewConfig]
    view: str | None = None
    days: int | None = None
    max_results: int | None = None
    offset: int | None = None
    width: int | None = None


@dataclass
class AppConfig:
    """Structured application configuration passed through ctx.obj."""

    config_path: str
    color_flag: bool | None
    verbose: bool
    todo_states: list[str]
    done_states: list[str]
    exclude: str | None
    exclude_inline: list[str] | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
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
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_level: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool
    filters: list[NamedQueryConfig]
    orderings: list[NamedQueryConfig]
    mutators: list[NamedQueryConfig]
    stats: StatsConfig
    tasks: TasksConfig
    capture: CaptureConfig
    agenda: AgendaConfig
    board: BoardConfig

    def custom_filter_map(self) -> dict[str, str]:
        """Return configured custom filters keyed by name."""
        return {item.name: item.query for item in self.filters}

    def custom_order_by_map(self) -> dict[str, str]:
        """Return configured custom orderings keyed by name."""
        return {item.name: item.query for item in self.orderings}

    def custom_with_map(self) -> dict[str, str]:
        """Return configured custom mutators keyed by name."""
        return {item.name: item.query for item in self.mutators}

    @property
    def capture_templates(self) -> dict[str, dict[str, str]]:
        """Compatibility accessor for capture templates."""
        return self.capture.templates

    @property
    def board_views(self) -> dict[str, BoardViewConfig]:
        """Compatibility accessor for board views."""
        return self.board.views

    @property
    def agenda_views(self) -> dict[str, AgendaViewConfig]:
        """Compatibility accessor for agenda views."""
        return self.agenda.views


class StatsDefaultMap(TypedDict):
    """Default map values for stats subcommands."""

    all: dict[str, object]
    summary: dict[str, object]
    tags: dict[str, object]
    groups: dict[str, object]


class TasksDefaultMap(TypedDict):
    """Default map values for tasks subcommands."""

    list: dict[str, object]
    query: dict[str, object]


class CliDefaultMap(TypedDict):
    """Top-level Typer Click default_map structure."""

    stats: StatsDefaultMap
    tasks: TasksDefaultMap
    board: dict[str, object]
    agenda: dict[str, object]


class ConfigDefaultsTarget(Protocol):
    """Protocol for args that accept inline defaults."""

    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None


class RootContext(Protocol):
    """Protocol for Click/Typer contexts with root-object access."""

    obj: object


class ContextWithRoot(Protocol):
    """Protocol for Click/Typer contexts exposing find_root()."""

    def find_root(self) -> RootContext:
        """Return the root Click/Typer context."""
        ...


def load_config(filepath: str) -> tuple[dict[str, object], bool]:
    """Load config from YAML file.

    Args:
        filepath: Path to config file

    Returns:
        Tuple of (config dict, malformed flag)
    """
    path = Path(filepath)
    try:
        with path.open(encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return ({}, False)
    except PermissionError:
        return ({}, True)
    except OSError:
        return ({}, True)
    except yaml.YAMLError:
        return ({}, True)

    if not isinstance(config, dict):
        return ({}, True)

    return (config, False)


def is_valid_date_argument(value: str) -> bool:
    """Check if date string is valid for parse_date_argument."""
    if not value or not value.strip():
        return False

    try:
        datetime.fromisoformat(value)
    except ValueError:
        try:
            datetime.fromisoformat(value.replace(" ", "T"))
        except ValueError:
            return False
        else:
            return True
    else:
        return True


def is_valid_keys_string(value: str) -> bool:
    """Check if comma-separated keys string is valid."""
    if not value or not value.strip():
        return False

    keys = [k.strip() for k in value.split(",") if k.strip()]
    if not keys:
        return False

    return all("|" not in key for key in keys)


def is_string_list(value: object) -> TypeGuard[list[str]]:
    """Check if value is list[str]."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_string_dict(value: object) -> TypeGuard[dict[str, str]]:
    """Check if value is dict[str, str]."""
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


def validate_int_option(value: object, min_value: int | None) -> int | None:
    """Validate integer option value."""
    if not isinstance(value, int):
        return None
    if min_value is not None and value < min_value:
        return None
    return value


def is_valid_regex(pattern: str, *, use_multiline: bool = False) -> bool:
    """Check if a string is a valid regex pattern."""
    try:
        if use_multiline:
            re.compile(pattern, re.MULTILINE)
        else:
            re.compile(pattern)
    except re.error:
        return False
    return True


def validate_str_option(key: str, value: object) -> str | None:
    """Validate string option value."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if key in ("--config", "--out", "--filter-priority", "--view") and not stripped:
        return None

    invalid_use = key == "--use" and value not in {"tags", "heading", "body"}
    invalid_keys = key in ("--todo-states", "--done-states") and not is_valid_keys_string(value)
    invalid_dates = key in (
        "--date",
        "--filter-date-from",
        "--filter-date-until",
    ) and not is_valid_date_argument(value)
    if invalid_use or invalid_keys or invalid_dates:
        return None
    return value


def validate_list_option(key: str, value: object) -> list[str] | None:
    """Validate list option value."""
    if not is_string_list(value):
        return None
    if key == "--filter-property" and any("=" not in item for item in value):
        return None
    if key == "--filter-tag" and any(not is_valid_regex(item) for item in value):
        return None
    if key == "--filter-heading" and any(not is_valid_regex(item) for item in value):
        return None
    if key == "--filter-body" and any(
        not is_valid_regex(item, use_multiline=True) for item in value
    ):
        return None
    return list(value)


def _parse_optional_string_field(
    section: dict[str, object],
    key: str,
    option_name: str,
) -> tuple[bool, str | None]:
    """Parse one optional string field from a config section."""
    if key not in section:
        return (True, None)
    value = validate_str_option(option_name, section[key])
    return (value is not None, value)


def _parse_optional_int_field(
    section: dict[str, object],
    key: str,
    min_value: int | None,
) -> tuple[bool, int | None]:
    """Parse one optional integer field from a config section."""
    if key not in section:
        return (True, None)
    value = validate_int_option(section[key], min_value)
    return (value is not None, value)


def _parse_optional_bool_field(
    section: dict[str, object],
    key: str,
) -> tuple[bool, bool | None]:
    """Parse one optional boolean field from a config section."""
    if key not in section:
        return (True, None)
    value = section[key]
    if not isinstance(value, bool):
        return (False, None)
    return (True, value)


def _parse_named_query_sections(
    config: dict[str, object],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]] | None:
    """Parse the custom filter/order-by/with sections."""
    filter_section = config.get("filter", {})
    order_by_section = config.get("order-by", {})
    with_section = config.get("with", {})
    if (
        not is_string_dict(filter_section)
        or not is_string_dict(order_by_section)
        or not is_string_dict(with_section)
    ):
        return None
    return (filter_section, order_by_section, with_section)


def _parse_optional_string_list_field(
    section: dict[str, object],
    key: str,
) -> tuple[bool, list[str] | None]:
    """Parse one optional raw string-list field from a config section."""
    if key not in section:
        return (True, None)
    value = section[key]
    if not is_string_list(value):
        return (False, None)
    return (True, list(value))


def _parse_shared_simple_entry(key: str, value: object) -> tuple[bool, dict[str, object]]:
    """Parse one simple shared top-level config entry."""
    if key == "color_flag":
        return (isinstance(value, bool), {key: value} if isinstance(value, bool) else {})

    bool_keys = {
        "verbose",
        "filter_completed",
        "filter_not_completed",
        "order_by_file_order",
        "order_by_file_order_reversed",
        "order_by_priority",
        "order_by_level",
        "order_by_timestamp_asc",
        "order_by_timestamp_desc",
        "with_tags_as_category",
    }
    if key in bool_keys:
        return (isinstance(value, bool), {key: value} if isinstance(value, bool) else {})

    int_keys = {"filter_level", "filter_repeats_above", "filter_repeats_below"}
    if key in int_keys:
        int_value = validate_int_option(value, None)
        return (int_value is not None, {key: int_value} if int_value is not None else {})

    string_options = {
        "filter_priority": "--filter-priority",
        "filter_date_from": "--filter-date-from",
        "filter_date_until": "--filter-date-until",
    }
    if key in string_options:
        str_value = validate_str_option(string_options[key], value)
        return (str_value is not None, {key: str_value} if str_value is not None else {})

    list_options = {
        "filter_properties": "--filter-property",
        "filter_tags": "--filter-tag",
        "filter_headings": "--filter-heading",
        "filter_bodies": "--filter-body",
    }
    if key in list_options:
        list_value = validate_list_option(list_options[key], value)
        return (list_value is not None, {key: list_value} if list_value is not None else {})

    return (True, {})


def _parse_shared_special_entry(key: str, value: object) -> tuple[bool, dict[str, object]]:
    """Parse one special shared top-level config entry."""
    if key == "todo_states":
        todo_states = validate_str_option("--todo-states", value)
        return (
            todo_states is not None,
            {key: _parse_state_list(todo_states)} if todo_states is not None else {},
        )
    if key == "done_states":
        done_states = validate_str_option("--done-states", value)
        return (
            done_states is not None,
            {key: _parse_state_list(done_states)} if done_states is not None else {},
        )
    if key == "mapping":
        return _parse_mapping_or_inline_entry(value)
    if key == "exclude":
        return _parse_exclude_or_inline_entry(value)
    return (True, {})


def _parse_mapping_or_inline_entry(value: object) -> tuple[bool, dict[str, object]]:
    """Parse one shared mapping entry from file or inline form."""
    if isinstance(value, str) and value.strip():
        return (True, {"mapping": value})
    if is_string_dict(value):
        return (True, {"mapping_inline": value})
    return (False, {})


def _parse_exclude_or_inline_entry(value: object) -> tuple[bool, dict[str, object]]:
    """Parse one shared exclude entry from file or inline form."""
    if isinstance(value, str) and value.strip():
        return (True, {"exclude": value})
    if is_string_list(value):
        return (True, {"exclude_inline": list(value)})
    return (False, {})


def parse_board_section(value: object) -> BoardConfig | None:
    """Parse board section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_board_keys = {"views", "view", "days", "max_results", "offset", "width"}
    if any(key not in allowed_board_keys for key in value):
        return None

    views: dict[str, BoardViewConfig] = {}
    if "views" in value:
        parsed_views = parse_board_views(value.get("views"))
        if parsed_views is None:
            return None
        views = parsed_views

    valid_view, view_name = _parse_optional_string_field(value, "view", "--view")
    valid_days, days = _parse_optional_int_field(value, "days", 1)
    valid_max_results, max_results = _parse_optional_int_field(value, "max_results", None)
    valid_offset, offset = _parse_optional_int_field(value, "offset", 0)
    valid_width, width = _parse_optional_int_field(value, "width", 50)
    if not all((valid_view, valid_days, valid_max_results, valid_offset, valid_width)):
        return None

    return BoardConfig(
        views=views,
        view=view_name,
        days=days,
        max_results=max_results,
        offset=offset,
        width=width,
    )


def parse_board_views(value: object) -> dict[str, BoardViewConfig] | None:
    """Parse board views list into a keyed map by view name."""
    if not isinstance(value, list):
        return None

    parsed_views: dict[str, BoardViewConfig] = {}
    for view_value in value:
        parsed_view = parse_board_view(view_value)
        if parsed_view is None:
            return None
        if parsed_view.name in parsed_views:
            return None
        parsed_views[parsed_view.name] = parsed_view

    return parsed_views


def parse_board_view(value: object) -> BoardViewConfig | None:
    """Parse one board view object."""
    if not isinstance(value, dict):
        return None

    allowed_view_keys = {"name", "columns"}
    if any(key not in allowed_view_keys for key in value):
        return None

    name_value = value.get("name")
    if not isinstance(name_value, str) or not name_value.strip():
        return None

    columns_value = value.get("columns")
    if not isinstance(columns_value, list) or not columns_value:
        return None

    parsed_columns: list[BoardColumnConfig] = []
    for column_value in columns_value:
        parsed_column = parse_board_column(column_value)
        if parsed_column is None:
            return None
        parsed_columns.append(parsed_column)

    return BoardViewConfig(name=name_value, columns=parsed_columns)


def parse_board_column(value: object) -> BoardColumnConfig | None:
    """Parse one board column object."""
    if not isinstance(value, dict):
        return None

    allowed_column_keys = {"name", "filter", "order-by"}
    if any(key not in allowed_column_keys for key in value):
        return None

    name_value = value.get("name")
    filter_value = value.get("filter")
    order_by_value = value.get("order-by")
    column_is_valid = (
        isinstance(name_value, str)
        and bool(name_value.strip())
        and isinstance(filter_value, str)
        and bool(filter_value.strip())
        and (
            order_by_value is None
            or (isinstance(order_by_value, str) and bool(order_by_value.strip()))
        )
    )
    if not column_is_valid:
        return None

    return BoardColumnConfig(
        name=cast("str", name_value),
        filter=cast("str", filter_value),
        order_by=cast("str | None", order_by_value),
    )


def parse_agenda_section(value: object) -> AgendaConfig | None:
    """Parse agenda section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_agenda_keys = {
        "views",
        "date",
        "days",
        "no_completed",
        "no_overdue",
        "no_upcoming",
        "future_repeats",
        "view",
        "max_results",
        "offset",
        "width",
    }
    if any(key not in allowed_agenda_keys for key in value):
        return None

    views: dict[str, AgendaViewConfig] = {}
    if "views" in value:
        parsed_views = parse_agenda_views(value.get("views"))
        if parsed_views is None:
            return None
        views = parsed_views

    valid_date, date = _parse_optional_string_field(value, "date", "--date")
    valid_days, days = _parse_optional_int_field(value, "days", 1)
    valid_view, view_name = _parse_optional_string_field(value, "view", "--view")
    valid_max_results, max_results = _parse_optional_int_field(value, "max_results", None)
    valid_offset, offset = _parse_optional_int_field(value, "offset", 0)
    valid_width, width = _parse_optional_int_field(value, "width", 50)
    valid_no_completed, no_completed = _parse_optional_bool_field(value, "no_completed")
    valid_no_overdue, no_overdue = _parse_optional_bool_field(value, "no_overdue")
    valid_no_upcoming, no_upcoming = _parse_optional_bool_field(value, "no_upcoming")
    valid_future_repeats, future_repeats = _parse_optional_bool_field(value, "future_repeats")
    if not all(
        (
            valid_date,
            valid_days,
            valid_view,
            valid_max_results,
            valid_offset,
            valid_width,
            valid_no_completed,
            valid_no_overdue,
            valid_no_upcoming,
            valid_future_repeats,
        ),
    ):
        return None

    return AgendaConfig(
        views=views,
        date=date,
        days=days,
        no_completed=no_completed,
        no_overdue=no_overdue,
        no_upcoming=no_upcoming,
        future_repeats=future_repeats,
        view=view_name,
        max_results=max_results,
        offset=offset,
        width=width,
    )


def parse_agenda_views(value: object) -> dict[str, AgendaViewConfig] | None:
    """Parse agenda views list into a keyed map by view name."""
    if not isinstance(value, list):
        return None

    parsed_views: dict[str, AgendaViewConfig] = {}
    for view_value in value:
        parsed_view = parse_agenda_view(view_value)
        if parsed_view is None:
            return None
        if parsed_view.name in parsed_views:
            return None
        parsed_views[parsed_view.name] = parsed_view

    return parsed_views


def parse_agenda_view(value: object) -> AgendaViewConfig | None:
    """Parse one agenda view object."""
    if not isinstance(value, dict):
        return None

    allowed_view_keys = {"name", "sections"}
    if any(key not in allowed_view_keys for key in value):
        return None

    name_value = value.get("name")
    if not isinstance(name_value, str) or not name_value.strip():
        return None

    sections_value = value.get("sections")
    if not isinstance(sections_value, list) or not sections_value:
        return None

    parsed_sections: list[AgendaSectionConfig] = []
    for section_value in sections_value:
        parsed_section = parse_agenda_section_config(section_value)
        if parsed_section is None:
            return None
        parsed_sections.append(parsed_section)

    return AgendaViewConfig(name=name_value, sections=parsed_sections)


def parse_agenda_section_config(value: object) -> AgendaSectionConfig | None:
    """Parse one agenda section config object."""
    if not isinstance(value, dict):
        return None

    allowed_section_keys = {"name", "filter", "order-by", "style", "timeline"}
    if any(key not in allowed_section_keys for key in value):
        return None

    name_value = value.get("name")
    filter_value = value.get("filter")
    order_by_value = value.get("order-by")
    style_value = value.get("style", "")
    timeline_value = value.get("timeline", False)

    section_is_valid = (
        isinstance(name_value, str)
        and bool(name_value.strip())
        and isinstance(filter_value, str)
        and bool(filter_value.strip())
        and (
            order_by_value is None
            or (isinstance(order_by_value, str) and bool(order_by_value.strip()))
        )
        and isinstance(style_value, str)
        and isinstance(timeline_value, bool)
    )
    if not section_is_valid:
        return None

    return AgendaSectionConfig(
        name=cast("str", name_value),
        filter=cast("str", filter_value),
        order_by=cast("str | None", order_by_value),
        style=cast("str", style_value),
        timeline=timeline_value,
    )


def parse_capture_templates_section(value: object) -> dict[str, dict[str, str]] | None:
    """Parse capture.templates section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_capture_keys = {"templates"}
    if any(key not in allowed_capture_keys for key in value):
        return None

    templates_value = value.get("templates", {})
    if not isinstance(templates_value, dict):
        return None

    parsed_templates: dict[str, dict[str, str]] = {}
    for template_name, template_value in templates_value.items():
        if not isinstance(template_name, str) or not template_name.strip():
            return None
        parsed_template = parse_capture_template(template_value)
        if parsed_template is None:
            return None
        parsed_templates[template_name] = parsed_template

    return parsed_templates


def parse_capture_template(value: object) -> dict[str, str] | None:
    """Parse one capture template object."""
    if not isinstance(value, dict):
        return None

    allowed_template_keys = {"file", "content", "parent"}
    file_value = value.get("file")
    content_value = value.get("content")
    parent_value = value.get("parent")

    template_is_valid = (
        not any(key not in allowed_template_keys for key in value)
        and "file" in value
        and "content" in value
        and isinstance(file_value, str)
        and bool(file_value.strip())
        and isinstance(content_value, str)
        and bool(content_value.strip())
        and (parent_value is None or isinstance(parent_value, str))
    )
    if not template_is_valid:
        return None

    parsed: dict[str, str] = {
        "file": cast("str", file_value),
        "content": cast("str", content_value),
    }
    if isinstance(parent_value, str) and parent_value.strip():
        parsed["parent"] = parent_value
    return parsed


def build_default_app_config(config_path: str = ".org-cli.yaml") -> AppConfig:
    """Build application config populated with code defaults."""
    return AppConfig(
        config_path=config_path,
        color_flag=None,
        verbose=False,
        todo_states=["TODO"],
        done_states=["DONE"],
        exclude=None,
        exclude_inline=None,
        mapping=None,
        mapping_inline=None,
        filter_priority=None,
        filter_level=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
        order_by_file_order=False,
        order_by_file_order_reversed=False,
        order_by_priority=False,
        order_by_level=False,
        order_by_timestamp_asc=False,
        order_by_timestamp_desc=False,
        with_tags_as_category=False,
        filters=[],
        orderings=[],
        mutators=[],
        stats=StatsConfig(),
        tasks=TasksConfig(),
        capture=CaptureConfig(templates={}),
        agenda=AgendaConfig(views={}),
        board=BoardConfig(views={}),
    )


def parse_shared_config(raw_config: dict[str, object]) -> dict[str, object] | None:
    """Parse shared top-level config values into AppConfig field values."""
    parsed: dict[str, object] = {}

    for key, value in raw_config.items():
        valid, parsed_value = _parse_shared_simple_entry(key, value)
        if not valid:
            return None
        if parsed_value:
            parsed.update(parsed_value)
            continue

        valid, parsed_value = _parse_shared_special_entry(key, value)
        if not valid:
            return None
        parsed.update(parsed_value)

    return parsed


def parse_stats_section(value: object) -> StatsConfig | None:
    """Parse stats section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_keys = {
        "max_results",
        "max_tags",
        "max_relations",
        "min_group_size",
        "max_groups",
        "use",
        "tags",
        "groups",
    }
    if any(key not in allowed_keys for key in value):
        return None

    config = StatsConfig()
    for key, min_value in {
        "max_results": None,
        "max_tags": 0,
        "max_relations": 0,
        "min_group_size": 0,
        "max_groups": 0,
    }.items():
        valid, int_value = _parse_optional_int_field(value, key, min_value)
        if not valid:
            return None
        setattr(config, key, int_value)

    valid_use, use_value = _parse_optional_string_field(value, "use", "--use")
    valid_tags, tags = _parse_optional_string_list_field(value, "tags")
    valid_groups, groups = _parse_optional_string_list_field(value, "groups")
    if not all((valid_use, valid_tags, valid_groups)):
        return None
    config.use = use_value
    config.tags = tags
    config.groups = groups

    return config


def parse_tasks_section(value: object) -> TasksConfig | None:
    """Parse tasks section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_keys = {"max_results", "details", "out", "out_theme", "pandoc_args"}
    if any(key not in allowed_keys for key in value):
        return None

    config = TasksConfig()
    valid_max_results, max_results = _parse_optional_int_field(value, "max_results", None)
    valid_details, details = _parse_optional_bool_field(value, "details")
    valid_out, out = _parse_optional_string_field(value, "out", "--out")
    if not all((valid_max_results, valid_details, valid_out)):
        return None
    if "out_theme" in value and not isinstance(value["out_theme"], str):
        return None
    if (
        "pandoc_args" in value
        and value["pandoc_args"] is not None
        and not isinstance(value["pandoc_args"], str)
    ):
        return None
    config.max_results = max_results
    config.details = details
    config.out = out
    config.out_theme = cast("str | None", value.get("out_theme"))
    config.pandoc_args = cast("str | None", value.get("pandoc_args"))

    return config


def _validate_top_level_config_keys(config: dict[str, object]) -> None:
    """Validate allowed top-level config keys."""
    allowed_keys = {
        "color_flag",
        "verbose",
        "todo_states",
        "done_states",
        "exclude",
        "mapping",
        "filter_priority",
        "filter_level",
        "filter_repeats_above",
        "filter_repeats_below",
        "filter_date_from",
        "filter_date_until",
        "filter_properties",
        "filter_tags",
        "filter_headings",
        "filter_bodies",
        "filter_completed",
        "filter_not_completed",
        "order_by_file_order",
        "order_by_file_order_reversed",
        "order_by_priority",
        "order_by_level",
        "order_by_timestamp_asc",
        "order_by_timestamp_desc",
        "with_tags_as_category",
        "filter",
        "order-by",
        "with",
        "capture",
        "board",
        "agenda",
        "stats",
        "tasks",
    }
    if any(key not in allowed_keys for key in config):
        raise typer.BadParameter("Malformed config")


def _parse_structured_sections(
    config: dict[str, object],
) -> tuple[
    dict[str, object],
    dict[str, dict[str, str]],
    BoardConfig,
    AgendaConfig,
    StatsConfig,
    TasksConfig,
]:
    """Parse structured top-level config sections into typed objects."""
    shared_config = parse_shared_config(config)
    if shared_config is None:
        raise typer.BadParameter("Malformed config")

    capture_templates = parse_capture_templates_section(config.get("capture", {}))
    if capture_templates is None:
        raise typer.BadParameter("Malformed config")

    board_config = _parse_optional_config_section(
        config,
        "board",
        parse_board_section,
        BoardConfig(views={}),
    )
    agenda_config = _parse_optional_config_section(
        config,
        "agenda",
        parse_agenda_section,
        AgendaConfig(views={}),
    )
    stats_config = _parse_optional_config_section(
        config,
        "stats",
        parse_stats_section,
        StatsConfig(),
    )
    tasks_config = _parse_optional_config_section(
        config,
        "tasks",
        parse_tasks_section,
        TasksConfig(),
    )

    return (
        shared_config,
        capture_templates,
        board_config,
        agenda_config,
        stats_config,
        tasks_config,
    )


def _parse_optional_config_section(
    config: dict[str, object],
    key: str,
    parser: Callable[[object], T | None],
    default: T,
) -> T:
    """Parse one optional config section, returning default when absent."""
    if key not in config:
        return default
    parsed = parser(config[key])
    if parsed is None:
        raise typer.BadParameter("Malformed config")
    return parsed


def _build_loaded_app_config(config: dict[str, object], config_path: Path) -> AppConfig:
    """Build AppConfig from one validated raw config object."""
    _validate_top_level_config_keys(config)

    named_query_sections = _parse_named_query_sections(config)
    if named_query_sections is None:
        raise typer.BadParameter("Malformed config")
    filter_section, order_by_section, with_section = named_query_sections
    (
        shared_config,
        capture_templates,
        board_config,
        agenda_config,
        stats_config,
        tasks_config,
    ) = _parse_structured_sections(config)

    app_config = build_default_app_config(str(config_path))
    for key, shared_value in shared_config.items():
        setattr(app_config, key, shared_value)

    app_config.filters = _named_query_list(filter_section)
    app_config.orderings = _named_query_list(order_by_section)
    app_config.mutators = _named_query_list(with_section)
    app_config.stats = stats_config
    app_config.tasks = tasks_config
    app_config.capture = CaptureConfig(templates=capture_templates)
    app_config.board = board_config
    app_config.agenda = agenda_config
    return app_config


def _parse_state_list(value: str) -> list[str]:
    """Parse comma-separated TODO/DONE state list from validated config string."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _apply_attr(target: object, dest: str, value: object, allowed: set[str]) -> bool:
    """Apply one value to a matching attribute name on a target object."""
    if dest not in allowed:
        return False
    setattr(target, dest, value)
    return True


def _apply_default_dest(config: AppConfig, dest: str, value: object) -> None:
    """Apply one validated config destination value onto AppConfig."""
    top_level_attrs = {
        "color_flag",
        "verbose",
        "filter_priority",
        "filter_level",
        "filter_repeats_above",
        "filter_repeats_below",
        "filter_date_from",
        "filter_date_until",
        "filter_completed",
        "filter_not_completed",
        "order_by_file_order",
        "order_by_file_order_reversed",
        "order_by_priority",
        "order_by_level",
        "order_by_timestamp_asc",
        "order_by_timestamp_desc",
        "with_tags_as_category",
    }
    agenda_attrs = {"date", "no_completed", "no_overdue", "no_upcoming", "future_repeats"}
    stats_attrs = {
        "mapping",
        "exclude",
        "mapping_inline",
        "exclude_inline",
        "max_tags",
        "max_relations",
        "min_group_size",
        "max_groups",
        "use",
    }
    tasks_attrs = {"details", "out", "out_theme", "pandoc_args"}

    if dest == "todo_states":
        config.todo_states = _parse_state_list(cast("str", value))
    elif dest == "done_states":
        config.done_states = _parse_state_list(cast("str", value))
    elif (
        _apply_attr(config, dest, value, top_level_attrs)
        or _apply_attr(config.agenda, dest, value, agenda_attrs)
        or _apply_attr(config.stats, dest, value, stats_attrs)
        or _apply_attr(config.tasks, dest, value, tasks_attrs)
    ):
        pass
    elif dest == "days":
        config.agenda.days = cast("int", value)
        config.board.days = cast("int", value)
    elif dest == "offset":
        config.agenda.offset = cast("int", value)
        config.board.offset = cast("int", value)
    elif dest == "width":
        config.agenda.width = cast("int", value)
        config.board.width = cast("int", value)
    elif dest == "view":
        config.agenda.view = cast("str", value)
        config.board.view = cast("str", value)
    elif dest == "max_results":
        limit = cast("int", value)
        config.stats.max_results = limit
        config.tasks.max_results = limit
        config.agenda.max_results = limit
        config.board.max_results = limit


def _apply_list_dest(config: AppConfig, dest: str, value: list[str]) -> None:
    """Apply one validated config list destination onto AppConfig."""
    if dest == "filter_properties":
        config.filter_properties = value
    elif dest == "filter_tags":
        config.filter_tags = value
    elif dest == "filter_headings":
        config.filter_headings = value
    elif dest == "filter_bodies":
        config.filter_bodies = value
    elif dest == "tags":
        config.stats.tags = value
    elif dest == "groups":
        config.stats.groups = value


def _named_query_list(items: dict[str, str]) -> list[NamedQueryConfig]:
    """Build stable named query config list from a mapping."""
    return [NamedQueryConfig(name=name, query=query) for name, query in items.items()]


def parse_config_argument(argv: list[str]) -> str:
    """Parse only the --config argument from argv."""
    default = ".org-cli.yaml"
    for idx, arg in enumerate(argv[1:], start=1):
        if arg == "--config" and idx + 1 < len(argv):
            return argv[idx + 1]
        if arg.startswith("--config="):
            return arg.split("=", 1)[1]
    return default


def load_cli_config(argv: list[str]) -> AppConfig:
    """Load config defaults from the configured file path."""
    config_name = parse_config_argument(argv)
    config_path = Path(config_name)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_name
    config, load_error = load_config(str(config_path))

    if load_error:
        raise typer.BadParameter("Malformed config")

    return _build_loaded_app_config(config, config_path)


def require_app_config(ctx: object) -> AppConfig:
    """Return AppConfig stored in the current root context."""
    root_context = cast("ContextWithRoot", ctx).find_root()
    app_config = root_context.obj
    if not isinstance(app_config, AppConfig):
        raise typer.BadParameter("Application config is not available")
    return app_config
