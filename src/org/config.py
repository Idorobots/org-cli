"""Configuration handling for the org CLI."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeGuard, cast


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
    "order_by",
    "todo_keys",
    "use",
    "with_gamify_category",
    "with_tags_as_category",
    "show",
    "groups",
    "verbose",
}


CONFIG_APPEND_DEFAULTS: dict[str, list[str]] = {}
CONFIG_INLINE_DEFAULTS: dict[str, object] = {}


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
        SystemExit: If file cannot be read
    """
    if filepath is None:
        return set()

    try:
        with open(filepath, encoding="utf-8") as f:
            return normalize_exclude_values(list(f))
    except FileNotFoundError:
        print(f"Error: Exclude list file '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied for '{filepath}'", file=sys.stderr)
        sys.exit(1)


def load_mapping(filepath: str | None) -> dict[str, str]:
    """Load tag mapping from a JSON file.

    Args:
        filepath: Path to JSON mapping file, or None for empty dict

    Returns:
        Dictionary mapping tags to canonical forms

    Raises:
        SystemExit: If file cannot be read or JSON is invalid
    """
    if filepath is None:
        return {}

    try:
        with open(filepath, encoding="utf-8") as f:
            mapping = json.load(f)

        if not isinstance(mapping, dict):
            print(f"Error: Mapping file '{filepath}' must contain a JSON object", file=sys.stderr)
            sys.exit(1)

        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                print(
                    f"Error: All keys and values in '{filepath}' must be strings",
                    file=sys.stderr,
                )
                sys.exit(1)

        return mapping

    except FileNotFoundError:
        print(f"Error: Mapping file '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied for '{filepath}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


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
    if key in ("--config", "--show") and not stripped:
        return None

    invalid_use = key == "--use" and value not in {"tags", "heading", "body"}
    invalid_order_by = key == "--order-by" and value not in {
        "timestamp-asc",
        "timestamp-desc",
        "gamify-exp-asc",
        "gamify-exp-desc",
    }
    invalid_keys = key in ("--todo-keys", "--done-keys") and not is_valid_keys_string(value)
    invalid_dates = key in (
        "--filter-date-from",
        "--filter-date-until",
    ) and not is_valid_date_argument(value)
    if invalid_use or invalid_order_by or invalid_keys or invalid_dates:
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


def apply_config_entry_by_options(
    key: str,
    value: object,
    defaults: dict[str, object],
    append_defaults: dict[str, list[str]],
    options: ConfigOptions,
) -> bool:
    """Apply a config entry using option metadata."""
    valid = True

    if key in options.int_options:
        dest, min_value = options.int_options[key]
        int_value = validate_int_option(value, min_value)
        if int_value is None:
            valid = False
        else:
            defaults[dest] = int_value
    elif key in options.bool_options:
        if not isinstance(value, bool):
            valid = False
        else:
            defaults[options.bool_options[key]] = value
    elif key in options.str_options:
        str_value = validate_str_option(key, value)
        if str_value is None:
            valid = False
        else:
            defaults[options.str_options[key]] = str_value
    elif key in options.list_options:
        list_value = validate_list_option(key, value)
        if list_value is None:
            valid = False
        else:
            append_defaults[options.list_options[key]] = list_value

    return valid


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
        "--filter-repeats-above": ("filter_repeats_above", None),
        "--filter-repeats-below": ("filter_repeats_below", None),
    }

    stats_bool_options: dict[str, str] = {
        "--with-gamify-category": "with_gamify_category",
        "--with-tags-as-category": "with_tags_as_category",
    }

    global_bool_options: dict[str, str] = {
        "--details": "details",
        "--filter-completed": "filter_completed",
        "--filter-not-completed": "filter_not_completed",
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
        "--order-by": "order_by",
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


def load_cli_config(
    argv: list[str],
) -> tuple[dict[str, object], dict[str, list[str]], dict[str, object]]:
    """Load config defaults from the configured file path."""
    config_name = parse_config_argument(argv)
    config_path = Path(config_name)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_name
    config, load_error = load_config(str(config_path))

    if load_error:
        print("Malformed config", file=sys.stderr)
        return ({}, {}, {})

    config_defaults = build_config_defaults(config)
    if config_defaults is None:
        print("Malformed config", file=sys.stderr)
        return ({}, {}, {})

    defaults, stats_defaults, append_defaults = config_defaults

    inline_defaults: dict[str, object] = {}
    for key in ("mapping_inline", "exclude_inline"):
        if key in defaults:
            inline_defaults[key] = defaults[key]

    combined_defaults = {**defaults, **stats_defaults}
    filtered_defaults = {
        key: value for key, value in combined_defaults.items() if key in COMMAND_OPTION_NAMES
    }

    return (filtered_defaults, append_defaults, inline_defaults)


def build_default_map(defaults: dict[str, object]) -> dict[str, dict[str, dict[str, object]]]:
    """Build Click default_map for Typer commands."""
    summary_defaults = dict(defaults)
    summary_defaults.pop("show", None)
    summary_defaults.pop("groups", None)

    stats_tasks_defaults = dict(defaults)
    for key in (
        "max_tags",
        "max_relations",
        "max_groups",
        "min_group_size",
        "use",
        "show",
        "groups",
    ):
        stats_tasks_defaults.pop(key, None)

    tasks_list_defaults = dict(defaults)
    for key in (
        "max_tags",
        "max_relations",
        "max_groups",
        "min_group_size",
        "use",
        "show",
        "groups",
        "buckets",
    ):
        tasks_list_defaults.pop(key, None)

    tags_defaults = dict(defaults)
    for key in ("max_tags", "max_groups", "min_group_size", "groups"):
        tags_defaults.pop(key, None)

    groups_defaults = dict(defaults)
    for key in ("max_tags", "max_groups", "min_group_size", "show"):
        groups_defaults.pop(key, None)

    return {
        "stats": {
            "summary": summary_defaults,
            "tasks": stats_tasks_defaults,
            "tags": tags_defaults,
            "groups": groups_defaults,
        },
        "tasks": {"list": tasks_list_defaults},
    }


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
