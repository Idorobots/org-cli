"""Configuration handling for the org CLI."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypedDict, TypeGuard, cast

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


CONFIG_APPEND_DEFAULTS: dict[str, list[str]] = {}
CONFIG_INLINE_DEFAULTS: dict[str, object] = {}
CONFIG_DEFAULTS: dict[str, object] = {}
CONFIG_CUSTOM_FILTERS: dict[str, str] = {}
CONFIG_CUSTOM_ORDER_BY: dict[str, str] = {}
CONFIG_CUSTOM_WITH: dict[str, str] = {}
CONFIG_CAPTURE_TEMPLATES: dict[str, dict[str, str]] = {}
CONFIG_BOARD_VIEWS: dict[str, BoardViewConfig] = {}
CONFIG_AGENDA_VIEWS: dict[str, AgendaViewConfig] = {}


DEST_TO_OPTION_NAME: dict[str, str] = {
    "date": "--date",
    "days": "--days",
    "color_flag": "--color/--no-color",
    "config": "--config",
    "details": "--details",
    "done_states": "--done-states",
    "exclude": "--exclude",
    "exclude_inline": "--exclude",
    "filter_bodies": "--filter-body",
    "filter_completed": "--filter-completed",
    "filter_date_from": "--filter-date-from",
    "filter_date_until": "--filter-date-until",
    "filter_priority": "--filter-priority",
    "filter_headings": "--filter-heading",
    "filter_level": "--filter-level",
    "filter_not_completed": "--filter-not-completed",
    "filter_properties": "--filter-property",
    "filter_repeats_above": "--filter-repeats-above",
    "filter_repeats_below": "--filter-repeats-below",
    "filter_tags": "--filter-tag",
    "groups": "--group",
    "mapping": "--mapping",
    "mapping_inline": "--mapping",
    "max_groups": "--max-groups",
    "max_relations": "--max-relations",
    "max_results": "--limit",
    "max_tags": "--max-tags",
    "min_group_size": "--min-group-size",
    "no_completed": "--no-completed",
    "no_overdue": "--no-overdue",
    "no_upcoming": "--no-upcoming",
    "future_repeats": "--future-repeats/--no-future-repeats",
    "offset": "--offset",
    "out": "--out",
    "out_theme": "--out-theme",
    "pandoc_args": "--pandoc-args",
    "order_by_file_order": "--order-by-file-order",
    "order_by_file_order_reversed": "--order-by-file-order-reversed",
    "order_by_priority": "--order-by-priority",
    "order_by_level": "--order-by-level",
    "order_by_timestamp_asc": "--order-by-timestamp-asc",
    "order_by_timestamp_desc": "--order-by-timestamp-desc",
    "tags": "--tag",
    "todo_states": "--todo-states",
    "use": "--use",
    "view": "--view",
    "verbose": "--verbose",
    "with_tags_as_category": "--with-tags-as-category",
    "width": "--width",
}


logger = logging.getLogger("org")


def normalize_exclude_values(values: list[str]) -> set[str]:
    """Normalize exclude values to match file-based behavior."""
    return {line.strip() for line in values if line.strip()}


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


@dataclass
class ConfigOptions:
    """Config option mapping metadata."""

    int_options: dict[str, tuple[str, int | None]]
    bool_options: dict[str, tuple[str, bool | None]]
    str_options: dict[str, str]
    list_options: dict[str, str]


@dataclass
class ConfigContext:
    """Config default targets and option metadata."""

    defaults: dict[str, object]
    stats_defaults: dict[str, object]
    append_defaults: dict[str, list[str]]
    global_options: ConfigOptions
    stats_options: ConfigOptions


@dataclass
class LoadedCliConfig:
    """Fully parsed CLI config payload."""

    defaults: dict[str, object]
    append_defaults: dict[str, list[str]]
    inline_defaults: dict[str, object]
    custom_filters: dict[str, str]
    custom_order_by: dict[str, str]
    custom_with: dict[str, str]
    capture_templates: dict[str, dict[str, str]]
    board_views: dict[str, BoardViewConfig]
    agenda_views: dict[str, AgendaViewConfig]


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


def parse_color_defaults(config: dict[str, object]) -> tuple[dict[str, object], bool]:
    """Parse color-related config defaults."""
    defaults: dict[str, object] = {}
    if "--color" in config and "--no-color" in config:
        return ({}, False)

    if "--color" in config:
        defaults["color_flag"] = True
    if "--no-color" in config:
        defaults["color_flag"] = False

    return (defaults, True)


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


def apply_mapping_config(value: object, defaults: dict[str, object]) -> bool:
    """Apply mapping config entry."""
    if isinstance(value, str):
        if not value.strip():
            return False
        defaults["mapping"] = value
        return True
    if is_string_dict(value):
        defaults["mapping_inline"] = value
        return True
    return False


def apply_exclude_config(value: object, defaults: dict[str, object]) -> bool:
    """Apply exclude config entry."""
    if isinstance(value, str):
        if not value.strip():
            return False
        defaults["exclude"] = value
        return True
    if is_string_list(value):
        defaults["exclude_inline"] = list(value)
        return True
    return False


def apply_int_option(
    value: object,
    dest: str,
    min_value: int | None,
    defaults: dict[str, object],
) -> bool:
    """Apply integer config option."""
    int_value = validate_int_option(value, min_value)
    if int_value is None:
        return False
    defaults[dest] = int_value
    return True


def apply_bool_option(
    value: object,
    dest: str,
    configured_value: bool | None,
    defaults: dict[str, object],
) -> bool:
    """Apply boolean config option."""
    if configured_value is None and not isinstance(value, bool):
        return False

    defaults[dest] = value if configured_value is None else configured_value
    return True


def apply_str_option(
    key: str,
    value: object,
    dest: str,
    defaults: dict[str, object],
) -> bool:
    """Apply string config option."""
    str_value = validate_str_option(key, value)
    if str_value is None:
        return False
    defaults[dest] = str_value
    return True


def apply_list_option(
    key: str,
    value: object,
    dest: str,
    append_defaults: dict[str, list[str]],
) -> bool:
    """Apply list config option."""
    list_value = validate_list_option(key, value)
    if list_value is None:
        return False
    append_defaults[dest] = list_value
    return True


def apply_config_entry_by_options(
    key: str,
    value: object,
    defaults: dict[str, object],
    append_defaults: dict[str, list[str]],
    options: ConfigOptions,
) -> bool:
    """Apply a config entry using option metadata."""
    if key in options.int_options:
        dest, min_value = options.int_options[key]
        return apply_int_option(value, dest, min_value, defaults)
    if key in options.bool_options:
        dest, configured_value = options.bool_options[key]
        return apply_bool_option(value, dest, configured_value, defaults)
    if key in options.str_options:
        return apply_str_option(key, value, options.str_options[key], defaults)
    if key in options.list_options:
        return apply_list_option(key, value, options.list_options[key], append_defaults)

    return True


def apply_config_entry(
    key: str,
    value: object,
    context: ConfigContext,
) -> bool:
    """Apply a config entry to defaults if valid."""
    if key == "--mapping":
        return apply_mapping_config(value, context.defaults)

    if key == "--exclude":
        return apply_exclude_config(value, context.defaults)

    option_sets = (
        (context.global_options, context.defaults),
        (context.stats_options, context.stats_defaults),
    )

    for options, defaults in option_sets:
        if (
            key in options.int_options
            or key in options.bool_options
            or key in options.str_options
            or key in options.list_options
        ):
            return apply_config_entry_by_options(
                key,
                value,
                defaults,
                context.append_defaults,
                options,
            )

    return False


def parse_config_sections(
    raw_config: dict[str, object],
) -> (
    tuple[
        dict[str, object],
        dict[str, str],
        dict[str, str],
        dict[str, str],
        dict[str, dict[str, str]],
        dict[str, BoardViewConfig],
        dict[str, AgendaViewConfig],
    ]
    | None
):
    """Parse top-level config sections.

    Accepted shape:
      {
        "defaults": { ... },
        "filter": {"name": "query"},
        "order-by": {"name": "query"},
        "with": {"name": "query"},
        "capture": {
          "templates": {
            "name": {
              "file": "path",
              "content": "* TODO {{title}}",
              "parent": ".id == 'project-1'"
            }
          }
        }
      }
    """
    allowed_keys = {"defaults", "filter", "order-by", "with", "capture", "board", "agenda"}
    defaults_section = raw_config.get("defaults", {})
    filter_section = raw_config.get("filter", {})
    order_by_section = raw_config.get("order-by", {})
    with_section = raw_config.get("with", {})

    sections_are_valid = (
        not any(key not in allowed_keys for key in raw_config)
        and isinstance(defaults_section, dict)
        and is_string_dict(filter_section)
        and is_string_dict(order_by_section)
        and is_string_dict(with_section)
    )
    if not sections_are_valid:
        return None

    capture_templates = parse_capture_templates_section(raw_config.get("capture", {}))
    if capture_templates is None:
        return None

    board_views: dict[str, BoardViewConfig] = {}
    if "board" in raw_config:
        parsed_board_views = parse_board_section(raw_config["board"])
        if parsed_board_views is None:
            return None
        board_views = parsed_board_views

    agenda_views: dict[str, AgendaViewConfig] = {}
    if "agenda" in raw_config:
        parsed_agenda_views = parse_agenda_section(raw_config["agenda"])
        if parsed_agenda_views is None:
            return None
        agenda_views = parsed_agenda_views

    return (
        cast("dict[str, object]", defaults_section),
        cast("dict[str, str]", filter_section),
        cast("dict[str, str]", order_by_section),
        cast("dict[str, str]", with_section),
        capture_templates,
        board_views,
        agenda_views,
    )


def parse_board_section(value: object) -> dict[str, BoardViewConfig] | None:
    """Parse board section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_board_keys = {"views"}
    if any(key not in allowed_board_keys for key in value):
        return None
    if "views" not in value:
        return None

    return parse_board_views(value.get("views"))


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


def parse_agenda_section(value: object) -> dict[str, AgendaViewConfig] | None:
    """Parse agenda section from top-level config value."""
    if not isinstance(value, dict):
        return None

    allowed_agenda_keys = {"views"}
    if any(key not in allowed_agenda_keys for key in value):
        return None
    if "views" not in value:
        return None

    return parse_agenda_views(value.get("views"))


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


def build_config_defaults(
    config: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, list[str]]] | None:
    """Validate config values and build defaults.

    Args:
        config: Raw config dict

    Returns:
        Tuple of (defaults, append_defaults) or None if malformed
    """
    defaults: dict[str, object] = {}
    stats_defaults: dict[str, object] = {}
    append_defaults: dict[str, list[str]] = {}
    valid = True

    color_defaults, color_valid = parse_color_defaults(config)
    if not color_valid:
        return None
    defaults.update(color_defaults)

    stats_int_options: dict[str, tuple[str, int | None]] = {
        "--limit": ("max_results", None),
        "--max-tags": ("max_tags", 0),
        "--max-relations": ("max_relations", 0),
        "--min-group-size": ("min_group_size", 0),
        "--max-groups": ("max_groups", 0),
    }

    global_int_options: dict[str, tuple[str, int | None]] = {
        "--days": ("days", 1),
        "--filter-level": ("filter_level", None),
        "--filter-repeats-above": ("filter_repeats_above", None),
        "--filter-repeats-below": ("filter_repeats_below", None),
        "--offset": ("offset", 0),
        "--width": ("width", 50),
    }

    stats_bool_options: dict[str, tuple[str, bool | None]] = {
        "--with-tags-as-category": ("with_tags_as_category", None),
    }

    global_bool_options: dict[str, tuple[str, bool | None]] = {
        "--details": ("details", None),
        "--filter-completed": ("filter_completed", None),
        "--filter-not-completed": ("filter_not_completed", None),
        "--no-completed": ("no_completed", None),
        "--no-overdue": ("no_overdue", None),
        "--no-upcoming": ("no_upcoming", None),
        "--future-repeats": ("future_repeats", True),
        "--no-future-repeats": ("future_repeats", False),
        "--order-by-file-order": ("order_by_file_order", None),
        "--order-by-file-order-reversed": ("order_by_file_order_reversed", None),
        "--order-by-level": ("order_by_level", None),
        "--order-by-priority": ("order_by_priority", None),
        "--order-by-timestamp-asc": ("order_by_timestamp_asc", None),
        "--order-by-timestamp-desc": ("order_by_timestamp_desc", None),
        "--verbose": ("verbose", None),
    }

    stats_str_options: dict[str, str] = {"--use": "use"}

    global_str_options: dict[str, str] = {
        "--date": "date",
        "--todo-states": "todo_states",
        "--done-states": "done_states",
        "--filter-date-from": "filter_date_from",
        "--filter-date-until": "filter_date_until",
        "--filter-priority": "filter_priority",
        "--out": "out",
        "--out-theme": "out_theme",
        "--pandoc-args": "pandoc_args",
        "--config": "config",
        "--view": "view",
    }

    global_list_options: dict[str, str] = {
        "--filter-property": "filter_properties",
        "--filter-tag": "filter_tags",
        "--filter-heading": "filter_headings",
        "--filter-body": "filter_bodies",
    }

    global_options = ConfigOptions(
        int_options=global_int_options,
        bool_options=global_bool_options,
        str_options=global_str_options,
        list_options=global_list_options,
    )

    stats_options = ConfigOptions(
        int_options=stats_int_options,
        bool_options=stats_bool_options,
        str_options=stats_str_options,
        list_options={"--group": "groups", "--tag": "tags"},
    )

    context = ConfigContext(
        defaults=defaults,
        stats_defaults=stats_defaults,
        append_defaults=append_defaults,
        global_options=global_options,
        stats_options=stats_options,
    )

    for key, value in config.items():
        if key in ("--color", "--no-color"):
            continue

        if not apply_config_entry(key, value, context):
            valid = False
            break

    if not valid:
        return None

    return (defaults, stats_defaults, append_defaults)


def parse_config_argument(argv: list[str]) -> str:
    """Parse only the --config argument from argv."""
    default = ".org-cli.yaml"
    for idx, arg in enumerate(argv[1:], start=1):
        if arg == "--config" and idx + 1 < len(argv):
            return argv[idx + 1]
        if arg.startswith("--config="):
            return arg.split("=", 1)[1]
    return default


def load_cli_config(argv: list[str]) -> LoadedCliConfig:
    """Load config defaults from the configured file path."""
    config_name = parse_config_argument(argv)
    config_path = Path(config_name)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_name
    config, load_error = load_config(str(config_path))

    if load_error:
        raise typer.BadParameter("Malformed config")

    config_sections = parse_config_sections(config)
    if config_sections is None:
        raise typer.BadParameter("Malformed config")

    (
        defaults_config,
        custom_filters,
        custom_order_by,
        custom_with,
        capture_templates,
        board_views,
        agenda_views,
    ) = config_sections

    config_defaults = build_config_defaults(defaults_config)
    if config_defaults is None:
        raise typer.BadParameter("Malformed config")

    defaults, stats_defaults, append_defaults = config_defaults

    inline_defaults: dict[str, object] = {}
    for key in ("mapping_inline", "exclude_inline"):
        if key in defaults:
            inline_defaults[key] = defaults[key]

    combined_defaults = {**defaults, **stats_defaults}
    filtered_defaults = {
        key: value for key, value in combined_defaults.items() if key in COMMAND_OPTION_NAMES
    }

    return LoadedCliConfig(
        defaults=filtered_defaults,
        append_defaults=append_defaults,
        inline_defaults=inline_defaults,
        custom_filters=custom_filters,
        custom_order_by=custom_order_by,
        custom_with=custom_with,
        capture_templates=capture_templates,
        board_views=board_views,
        agenda_views=agenda_views,
    )


def build_default_map(defaults: dict[str, object]) -> CliDefaultMap:
    """Build Click default_map for Typer commands."""
    all_defaults = {key: value for key, value in defaults.items() if key not in {"tags", "groups"}}

    task_command_disallowed = {
        "max_tags",
        "max_relations",
        "max_groups",
        "min_group_size",
        "use",
        "tags",
        "groups",
    }
    stats_tasks_defaults = {
        key: value for key, value in defaults.items() if key not in task_command_disallowed
    }
    tasks_list_defaults = {
        key: value for key, value in defaults.items() if key not in task_command_disallowed
    }
    tasks_query_defaults = {
        key: value for key, value in defaults.items() if key not in task_command_disallowed
    }
    board_disallowed = task_command_disallowed.union(
        {"details", "out", "out_theme", "pandoc_args"},
    )
    board_defaults = {key: value for key, value in defaults.items() if key not in board_disallowed}
    agenda_disallowed = task_command_disallowed.union(
        {"details", "out", "out_theme", "pandoc_args"},
    )
    agenda_defaults = {
        key: value for key, value in defaults.items() if key not in agenda_disallowed
    }
    tags_defaults = {
        key: value
        for key, value in defaults.items()
        if key not in {"max_tags", "max_groups", "min_group_size", "groups"}
    }

    groups_defaults = {
        key: value
        for key, value in defaults.items()
        if key not in {"max_tags", "max_groups", "min_group_size", "tags"}
    }

    return {
        "stats": {
            "all": all_defaults,
            "summary": stats_tasks_defaults,
            "tags": tags_defaults,
            "groups": groups_defaults,
        },
        "tasks": {"list": tasks_list_defaults, "query": tasks_query_defaults},
        "board": board_defaults,
        "agenda": agenda_defaults,
    }


def _format_default_log_entry(option_name: str, value: object) -> str:
    """Format one option/value pair for config-default logging."""
    return f"{option_name}={value!r}"


def _format_argument_log_entry(arg_name: str, value: object) -> str:
    """Format one argument/value pair for command argument logging."""
    return f"{arg_name}={value!r}"


def _redact_inline_config_value(option_name: str, value: object) -> object:
    """Redact inline mapping/exclude values in default logs."""
    if option_name in {"--mapping", "--exclude"} and isinstance(value, (dict, list)):
        return "<Value ellided...>"
    return value


def log_applied_config_defaults(_args: object, _argv: list[str], command_name: str) -> None:
    """Log config defaults loaded from config file."""
    if not logger.isEnabledFor(logging.INFO):
        return

    entries: list[str] = []

    for dest, default_value in sorted(CONFIG_DEFAULTS.items(), key=lambda item: item[0]):
        option_name = DEST_TO_OPTION_NAME.get(dest)
        if option_name is None:
            continue
        entries.append(
            _format_default_log_entry(
                option_name,
                _redact_inline_config_value(option_name, default_value),
            ),
        )

    for dest, values in sorted(CONFIG_APPEND_DEFAULTS.items(), key=lambda item: item[0]):
        option_name = DEST_TO_OPTION_NAME.get(dest)
        if option_name is None:
            continue
        entries.append(
            _format_default_log_entry(
                option_name,
                _redact_inline_config_value(option_name, values),
            ),
        )

    for dest, option_name in (
        ("mapping_inline", "--mapping"),
        ("exclude_inline", "--exclude"),
    ):
        inline_value = CONFIG_INLINE_DEFAULTS.get(dest)
        if inline_value is None:
            continue
        entries.append(_format_default_log_entry(option_name, "<Value ellided...>"))

    if entries:
        logger.info("Config defaults applied (%s): %s", command_name, ", ".join(entries))


def log_command_arguments(args: object, command_name: str) -> None:
    """Log all final argument values used to run a command."""
    if not logger.isEnabledFor(logging.INFO):
        return

    try:
        arg_items = vars(args).items()
    except TypeError:
        return

    entries = [
        _format_argument_log_entry(arg_name, arg_value)
        for arg_name, arg_value in sorted(arg_items, key=lambda item: item[0])
    ]
    logger.info("Command arguments (%s): %s", command_name, ", ".join(entries))


def apply_config_defaults(args: object) -> None:
    """Apply config-provided defaults for append and inline values."""
    for dest, values in CONFIG_APPEND_DEFAULTS.items():
        if not hasattr(args, dest):
            continue
        if getattr(args, dest, None) is None:
            setattr(args, dest, values)

    mapping_inline = cast("dict[str, str] | None", CONFIG_INLINE_DEFAULTS.get("mapping_inline"))
    exclude_inline = cast("list[str] | None", CONFIG_INLINE_DEFAULTS.get("exclude_inline"))
    if hasattr(args, "mapping_inline"):
        target = cast("ConfigDefaultsTarget", args)
        target.mapping_inline = mapping_inline if mapping_inline is not None else None
    if hasattr(args, "exclude_inline"):
        target = cast("ConfigDefaultsTarget", args)
        target.exclude_inline = exclude_inline if exclude_inline is not None else None
