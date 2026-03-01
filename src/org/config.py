"""Configuration handling for the org CLI."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeGuard, cast

import typer


COMMAND_OPTION_NAMES = {
    "buckets",
    "category_property",
    "color_flag",
    "config",
    "details",
    "done_keys",
    "exclude",
    "filter_bodies",
    "filter_completed",
    "filter_date_from",
    "filter_date_until",
    "filter_gamify_exp_above",
    "filter_gamify_exp_below",
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
    "offset",
    "out",
    "out_theme",
    "pandoc_args",
    "order_by_file_order",
    "order_by_file_order_reversed",
    "order_by_gamify_exp_asc",
    "order_by_gamify_exp_desc",
    "order_by_level",
    "order_by_timestamp_asc",
    "order_by_timestamp_desc",
    "todo_keys",
    "use",
    "with_gamify_category",
    "with_numeric_gamify_exp",
    "with_tags_as_category",
    "show",
    "groups",
    "verbose",
}


CONFIG_APPEND_DEFAULTS: dict[str, list[str]] = {}
CONFIG_INLINE_DEFAULTS: dict[str, object] = {}
CONFIG_DEFAULTS: dict[str, object] = {}
CONFIG_CUSTOM_FILTERS: dict[str, str] = {}
CONFIG_CUSTOM_ORDER_BY: dict[str, str] = {}
CONFIG_CUSTOM_WITH: dict[str, str] = {}


DEST_TO_OPTION_NAME: dict[str, str] = {
    "buckets": "--buckets",
    "category_property": "--category-property",
    "color_flag": "--color/--no-color",
    "config": "--config",
    "details": "--details",
    "done_keys": "--done-keys",
    "exclude": "--exclude",
    "exclude_inline": "--exclude",
    "filter_bodies": "--filter-body",
    "filter_completed": "--filter-completed",
    "filter_date_from": "--filter-date-from",
    "filter_date_until": "--filter-date-until",
    "filter_gamify_exp_above": "--filter-gamify-exp-above",
    "filter_gamify_exp_below": "--filter-gamify-exp-below",
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
    "max_results": "--max-results",
    "max_tags": "--max-tags",
    "min_group_size": "--min-group-size",
    "offset": "--offset",
    "out": "--out",
    "out_theme": "--out-theme",
    "pandoc_args": "--pandoc-args",
    "order_by_file_order": "--order-by-file-order",
    "order_by_file_order_reversed": "--order-by-file-order-reversed",
    "order_by_gamify_exp_asc": "--order-by-gamify-exp-asc",
    "order_by_gamify_exp_desc": "--order-by-gamify-exp-desc",
    "order_by_level": "--order-by-level",
    "order_by_timestamp_asc": "--order-by-timestamp-asc",
    "order_by_timestamp_desc": "--order-by-timestamp-desc",
    "show": "--show",
    "todo_keys": "--todo-keys",
    "use": "--use",
    "verbose": "--verbose",
    "with_gamify_category": "--with-gamify-category",
    "with_numeric_gamify_exp": "--with-numeric-gamify-exp",
    "with_tags_as_category": "--with-tags-as-category",
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

    try:
        with open(filepath, encoding="utf-8") as f:
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

    try:
        with open(filepath, encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            raise typer.BadParameter(f"Mapping file '{filepath}' must contain a JSON object")

        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise typer.BadParameter(f"All keys and values in '{filepath}' must be strings")

        return mapping

    except FileNotFoundError as err:
        raise typer.BadParameter(f"Mapping file '{filepath}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{filepath}'") from err
    except json.JSONDecodeError as err:
        raise typer.BadParameter(f"Invalid JSON in '{filepath}': {err}") from err


@dataclass
class ConfigOptions:
    """Config option mapping metadata."""

    int_options: dict[str, tuple[str, int | None]]
    bool_options: dict[str, str]
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


class ConfigDefaultsTarget(Protocol):
    """Protocol for args that accept inline defaults."""

    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None


def load_config(filepath: str) -> tuple[dict[str, object], bool]:
    """Load config from JSON file.

    Args:
        filepath: Path to config file

    Returns:
        Tuple of (config dict, malformed flag)
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        return ({}, False)
    except PermissionError:
        return ({}, True)
    except OSError:
        return ({}, True)
    except json.JSONDecodeError:
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
        return True
    except ValueError:
        pass

    try:
        datetime.fromisoformat(value.replace(" ", "T"))
        return True
    except ValueError:
        return False


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
    color_value = config.get("--color")
    no_color_value = config.get("--no-color")

    if "--color" in config and not isinstance(color_value, bool):
        return ({}, False)
    if "--no-color" in config and not isinstance(no_color_value, bool):
        return ({}, False)
    if (
        isinstance(color_value, bool)
        and isinstance(no_color_value, bool)
        and color_value
        and no_color_value
    ):
        return ({}, False)

    if color_value is True:
        defaults["color_flag"] = True
    if no_color_value is True:
        defaults["color_flag"] = False

    return (defaults, True)


def validate_int_option(value: object, min_value: int | None) -> int | None:
    """Validate integer option value."""
    if not isinstance(value, int):
        return None
    if min_value is not None and value < min_value:
        return None
    return value


def is_valid_regex(pattern: str, use_multiline: bool = False) -> bool:
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
    if key in ("--config", "--show", "--out") and not stripped:
        return None

    invalid_use = key == "--use" and value not in {"tags", "heading", "body"}
    invalid_keys = key in ("--todo-keys", "--done-keys") and not is_valid_keys_string(value)
    invalid_dates = key in (
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


def apply_bool_option(value: object, dest: str, defaults: dict[str, object]) -> bool:
    """Apply boolean config option."""
    if not isinstance(value, bool):
        return False
    defaults[dest] = value
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
        return apply_bool_option(value, options.bool_options[key], defaults)
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
                key, value, defaults, context.append_defaults, options
            )

    return False


def parse_config_sections(
    raw_config: dict[str, object],
) -> tuple[dict[str, object], dict[str, str], dict[str, str], dict[str, str]] | None:
    """Parse top-level config sections.

    Accepted shape:
      {
        "defaults": { ... },
        "filter": {"name": "query"},
        "order-by": {"name": "query"},
        "with": {"name": "query"}
      }
    """
    allowed_keys = {"defaults", "filter", "order-by", "with"}
    if any(key not in allowed_keys for key in raw_config):
        return None

    defaults_section = raw_config.get("defaults", {})
    if not isinstance(defaults_section, dict):
        return None

    filter_section = raw_config.get("filter", {})
    if not is_string_dict(filter_section):
        return None

    order_by_section = raw_config.get("order-by", {})
    if not is_string_dict(order_by_section):
        return None

    with_section = raw_config.get("with", {})
    if not is_string_dict(with_section):
        return None

    return (
        cast(dict[str, object], defaults_section),
        dict(filter_section),
        dict(order_by_section),
        dict(with_section),
    )


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
        "--max-results": ("max_results", None),
        "--max-tags": ("max_tags", 0),
        "--max-relations": ("max_relations", 0),
        "--min-group-size": ("min_group_size", 0),
        "--max-groups": ("max_groups", 0),
        "--buckets": ("buckets", 20),
    }

    global_int_options: dict[str, tuple[str, int | None]] = {
        "--filter-gamify-exp-above": ("filter_gamify_exp_above", None),
        "--filter-gamify-exp-below": ("filter_gamify_exp_below", None),
        "--filter-level": ("filter_level", None),
        "--filter-repeats-above": ("filter_repeats_above", None),
        "--filter-repeats-below": ("filter_repeats_below", None),
        "--offset": ("offset", 0),
    }

    stats_bool_options: dict[str, str] = {
        "--with-gamify-category": "with_gamify_category",
        "--with-numeric-gamify-exp": "with_numeric_gamify_exp",
        "--with-tags-as-category": "with_tags_as_category",
    }

    global_bool_options: dict[str, str] = {
        "--details": "details",
        "--filter-completed": "filter_completed",
        "--filter-not-completed": "filter_not_completed",
        "--order-by-file-order": "order_by_file_order",
        "--order-by-file-order-reversed": "order_by_file_order_reversed",
        "--order-by-gamify-exp-asc": "order_by_gamify_exp_asc",
        "--order-by-gamify-exp-desc": "order_by_gamify_exp_desc",
        "--order-by-level": "order_by_level",
        "--order-by-timestamp-asc": "order_by_timestamp_asc",
        "--order-by-timestamp-desc": "order_by_timestamp_desc",
        "--verbose": "verbose",
    }

    stats_str_options: dict[str, str] = {
        "--category-property": "category_property",
        "--use": "use",
        "--show": "show",
    }

    global_str_options: dict[str, str] = {
        "--todo-keys": "todo_keys",
        "--done-keys": "done_keys",
        "--filter-date-from": "filter_date_from",
        "--filter-date-until": "filter_date_until",
        "--out": "out",
        "--out-theme": "out_theme",
        "--pandoc-args": "pandoc_args",
        "--config": "config",
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
        list_options={"--group": "groups"},
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
    default = ".org-cli.json"
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

    defaults_config, custom_filters, custom_order_by, custom_with = config_sections

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
    )


def build_default_map(defaults: dict[str, object]) -> dict[str, dict[str, dict[str, object]]]:
    """Build Click default_map for Typer commands."""
    summary_defaults = {
        key: value for key, value in defaults.items() if key not in {"show", "groups"}
    }

    task_command_disallowed = {
        "max_tags",
        "max_relations",
        "max_groups",
        "min_group_size",
        "use",
        "show",
        "groups",
    }
    stats_tasks_defaults = {
        key: value for key, value in defaults.items() if key not in task_command_disallowed
    }
    tasks_list_defaults = {
        key: value for key, value in defaults.items() if key not in task_command_disallowed
    }
    tags_defaults = {
        key: value
        for key, value in defaults.items()
        if key not in {"max_tags", "max_groups", "min_group_size", "groups"}
    }

    groups_defaults = {
        key: value
        for key, value in defaults.items()
        if key not in {"max_tags", "max_groups", "min_group_size", "show"}
    }

    return {
        "stats": {
            "summary": summary_defaults,
            "tasks": stats_tasks_defaults,
            "tags": tags_defaults,
            "groups": groups_defaults,
        },
        "tasks": {"list": tasks_list_defaults},
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
                option_name, _redact_inline_config_value(option_name, default_value)
            )
        )

    for dest, values in sorted(CONFIG_APPEND_DEFAULTS.items(), key=lambda item: item[0]):
        option_name = DEST_TO_OPTION_NAME.get(dest)
        if option_name is None:
            continue
        entries.append(
            _format_default_log_entry(option_name, _redact_inline_config_value(option_name, values))
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

    mapping_inline = cast(dict[str, str] | None, CONFIG_INLINE_DEFAULTS.get("mapping_inline"))
    exclude_inline = cast(list[str] | None, CONFIG_INLINE_DEFAULTS.get("exclude_inline"))
    if hasattr(args, "mapping_inline"):
        target = cast(ConfigDefaultsTarget, args)
        target.mapping_inline = mapping_inline if mapping_inline is not None else None
    if hasattr(args, "exclude_inline"):
        target = cast(ConfigDefaultsTarget, args)
        target.exclude_inline = exclude_inline if exclude_inline is not None else None
