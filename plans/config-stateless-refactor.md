# Stateless Configuration Refactor Plan

## Goals

- Load configuration before building the command tree.
- Use `ctx.obj` to carry configuration through command execution.
- Eliminate global configuration storage and make commands stateless.
- Include output-affecting CLI settings such as `--color` and `--verbose` in `AppConfig`.
- Remove the legacy `defaults` bag entirely if feasible during the refactor.

## Target Flow

1. Create a well-defined structured configuration object.
2. Populate that object with code defaults.
3. Determine the configuration file path.
4. Load and validate the configuration file sections.
5. Merge file values into the structured configuration object.
6. Build the Typer command tree after configuration is loaded.
7. Pass the configuration object through `ctx.obj`.
8. In each command, derive an effective command config by overlaying CLI switch values.
9. Log the effective config object.
10. Execute the command using values from that resulting config only.

## Configuration Shape

Introduce a structured `AppConfig` model and supporting dataclasses. The final shape should cover:

- `color: bool | None`
- `verbose: bool`
- `todo_states: list[str]`
- `done_states: list[str]`
- `filters: list[...]`
- `orderings: list[...]`
- `mutators: list[...]`
- `stats.exclude: str | None`
- `stats.mapping: str | None`
- `capture.templates: ...`
- `agenda.views: ...`
- `board.views: ...`

If some transitional compatibility is needed while the refactor is in progress, keep it narrow and local. The end goal is to remove the old `defaults` dict entirely.

## Main Refactor Steps

### 1. Introduce Structured Config Types

- Add `AppConfig` and nested config dataclasses in `src/org/config/app.py`.
- Represent file-backed sections directly instead of storing them in module globals.
- Include `color` and `verbose` in the structured config.
- Replace `LoadedCliConfig` with a structured load result based on `AppConfig`.

### 2. Split Config Loading Into Explicit Stages

- Add helpers for:
  - code-default construction
  - config path resolution
  - raw YAML loading
  - section parsing
  - structured merge/update
- Validate each section against a well-defined schema.
- Populate dedicated fields such as `todo_states` and `done_states` directly instead of mirroring them through a generic defaults map.

### 3. Build The CLI After Config Load

- Update `src/org/cli.py` so `main()` loads config first.
- Build and register the command tree after config is loaded.
- Store the loaded config in `ctx.obj`.
- Remove all writes to `CONFIG_*` globals and `DEFAULT_VERBOSE`.

### 4. Replace Global Default Application

- Remove `apply_config_defaults(args)` in its current global-state form.
- Introduce an explicit command overlay step that accepts `AppConfig` and CLI args.
- Prefer command-specific structured fields over any generic/default fallback.
- Ensure CLI switch values override file config values only where the user provided them.

### 5. Refactor Query-Pipeline Config Access

- Update `src/org/config/cli.py` helpers to accept `AppConfig` explicitly.
- Thread config into:
  - `validate_custom_switches`
  - `normalize_cli_files_for_custom_switches`
  - `parse_filter_entries_from_argv`
  - `parse_order_entries_from_argv`
  - `parse_with_entries_from_argv`
  - `build_pipeline_stages`
- Read custom filters/orderings/mutators from structured config instead of globals.

### 6. Refactor Command Consumers

- Update commands and helpers that currently read global config:
  - stats commands
  - tasks commands
  - board commands
  - agenda commands
  - capture commands
- Pass config explicitly into:
  - mapping/exclude resolution
  - board view resolution
  - agenda view resolution
  - capture template resolution
  - prompt/template-name helpers

### 7. Update Logging

- Change config logging helpers to accept `AppConfig` or the effective command config explicitly.
- Log the effective config object rather than reconstructing defaults from globals.
- Keep inline-value redaction behavior where needed.

### 8. Remove Legacy Global State

- Delete module-level config stores such as:
  - `CONFIG_APPEND_DEFAULTS`
  - `CONFIG_INLINE_DEFAULTS`
  - `CONFIG_DEFAULTS`
  - `CONFIG_CUSTOM_FILTERS`
  - `CONFIG_CUSTOM_ORDER_BY`
  - `CONFIG_CUSTOM_WITH`
  - `CONFIG_CAPTURE_TEMPLATES`
  - `CONFIG_BOARD_VIEWS`
  - `CONFIG_AGENDA_VIEWS`
  - `DEFAULT_VERBOSE`
- Remove remaining runtime dependencies on those names.

### 9. Remove Legacy `defaults` If Feasible

- Prefer deleting the old top-level `defaults` representation entirely.
- If full removal is too disruptive for one change, isolate any temporary compatibility layer to config loading only.
- Do not let runtime command execution depend on a generic `defaults` bag.

### 10. Update Tests

- Replace tests that monkeypatch global config with tests that construct explicit `AppConfig` values.
- Update CLI tests to verify:
  - config is loaded before command registration/execution
  - config is passed via `ctx.obj`
  - command-local overlays produce the effective config
- Update query-pipeline tests to pass config explicitly.
- Update capture/board/agenda tests to pass templates/views explicitly instead of mutating globals.

## Implementation Order

1. Add `AppConfig` and config-loading/merging helpers.
2. Refactor `org.cli` to load config first and inject it through `ctx.obj`.
3. Refactor `org.config.cli` to accept config explicitly.
4. Refactor logging and command overlay/default resolution.
5. Refactor capture, board, and agenda config consumers.
6. Remove remaining globals and legacy paths.
7. Update tests.
8. Run `poetry run task check`.

## Key Constraints

- Prefer small, local changes over broad rewrites where possible.
- Keep commands stateless: no runtime dependence on module globals.
- Treat the structured config object as the single source of truth.
- Use `ctx.obj` for config propagation for now.
- Prefer command-specific fields over generic storage.
