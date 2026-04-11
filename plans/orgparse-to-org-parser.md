# Migration plan: orgparse -> org-parser

Replace `orgparse` with `org-parser` across runtime code, CLI behavior, docs,
and tests.

---

## Decisions locked in

These project decisions are part of this migration and should be implemented as
breaking changes:

1. Backwards compatibility is **not required**.
2. Query/runtime field names should use real org-parser names (no shims).
3. Built-in filters/order-by query fragments must be updated to new names.
4. `category_property` support is removed from code and CLI.
5. Category handling uses `Heading.category` directly.

---

## Core mapping

### Types

| orgparse | org-parser |
|---|---|
| `OrgRootNode` | `Document` |
| `OrgNode` | `Heading` |
| `OrgEnv` | merged into `Document` |
| `OrgDate` | `Timestamp` |
| `OrgDateClock` | `Clock` |
| `OrgDateRepeatedTask` | `Repeat` |

### Attributes / fields

| old | new |
|---|---|
| `root[1:]` | `list(document)` |
| `root.env.todo_keys` | `document.todo_states` |
| `root.env.done_keys` | `document.done_states` |
| `root.env.all_todo_keys` | `document.all_states` |
| `node.env.filename` | `node.document.filename` |
| `node.heading` | `node.title_text` |
| `node.body` | `node.body_text` |
| `node.repeated_tasks` | `node.repeats` |
| `node.shallow_tags` | `node.heading_tags` |
| `node.datelist` | `node.timestamps` |
| `node.clock` | `node.clock_entries` |
| `node.linenumber` | `node.line` |
| `rt.start` | `rt.timestamp.start` |
| `OrgDate.is_active()` | `timestamp.is_active` |

### Query-language field names (breaking)

These names must be used everywhere in built-in query fragments and docs:

| old query field | new query field |
|---|---|
| `.heading` | `.title_text` |
| `.body` | `.body_text` |
| `.repeated_tasks` | `.repeats` |

Also update compound expressions accordingly, for example:

- `.repeated_tasks + .deadline + .closed + .scheduled`
- becomes
- `.repeats + .deadline + .closed + .scheduled`

### Category model

- Remove `category_property` argument/plumbing.
- Read category from `node.category`.
- `--with-tags-as-category` (if kept) should set `node.category = node.tags[0]`.
- Remove property-drawer rewriting for category projection.

---

## File-by-file implementation

### Dependency and packaging

#### `pyproject.toml`
- Remove `orgparse`.
- Add `org-parser` pinned to current stable release.

#### `poetry.lock`
- Regenerate lockfile after dependency swap.

### Core loading and timestamp extraction

#### `src/org/parse.py`
- `import orgparse` -> `import org_parser`.
- `OrgRootNode`/`OrgNode` annotations -> `Document`/`Heading`.
- `orgparse.loads(...)` -> `org_parser.loads(...)`.
- `root.env.todo_keys` -> `document.todo_states`.
- `root.env.done_keys` -> `document.done_states`.

#### `src/org/timestamp.py`
- Use `Heading` and `Repeat` types.
- `node.repeated_tasks` -> `node.repeats`.
- `rt.start` -> `rt.timestamp.start`.
- `node.datelist` -> `node.timestamps`.
- Remove now-invalid `Timestamp.start` truthiness guards.

### Filtering, analysis, shared query construction

#### `src/org/filters.py`
- Remove wrapper classes (`_FilteredOrgNode`, `_PropertyRewrittenOrgNode`).
- Migrate all type annotations to `Heading`/`Repeat`.
- In-place mutation behavior for `_filter_node_repeats` on `node.repeats`.
- Rename heading/body/repeat access to new attributes.
- Completion filters use `node.document.done_states` / `node.document.todo_states`.
- `preprocess_tags_as_category` mutates `node.category` directly.
- Remove `filter_category`'s `category_property` usage; either:
  - simplify to effective category filtering on `node.category`, or
  - remove function entirely if unused.

#### `src/org/analyze.py`
- All `OrgNode` types -> `Heading`.
- `.heading`/`.body`/`.repeated_tasks` -> `.title_text`/`.body_text`/`.repeats`.
- `compute_category_histogram` signature drops `category_property` and uses
  `node.category`.
- `analyze(...)` signature drops `category_property` parameter.

#### `src/org/cli_common.py`
- `OrgRootNode`/`OrgNode` -> `Document`/`Heading`.
- `root[1:]` -> `list(root)`.
- `isinstance(..., OrgNode)` -> `isinstance(..., Heading)`.
- Remove `category_property` from protocols, context vars, and function calls.
- Update built-in filter/order query text:
  - `.heading` -> `.title_text`
  - `.body` -> `.body_text`
  - `.repeated_tasks` -> `.repeats`
- Keep built-in semantics; only rename fields and remove category-property plumbing.

### Rendering and object export

#### `src/org/tui.py`
- `OrgNode` annotations -> `Heading`.
- `node.env.filename` -> `node.document.filename`.
- `node.heading` -> `node.title_text`.

#### `src/org/output_format.py`
- Replace orgparse imports with `Document`, `Heading`, `Timestamp`, `Clock`, `Repeat`.
- Remove OrgDate falsy branch.
- Export real org-parser field names only (no aliases).
- Update type dispatch and JSON conversion type checks to org-parser classes.

### Commands

#### `src/org/commands/query.py`
- Replace orgparse imports and isinstance checks with org-parser classes.
- `value.env.filename` -> `value.document.filename` (Heading) / `value.filename` (Document).
- Remove OrgDate falsy branch.

#### `src/org/commands/tasks/list.py`
- `OrgNode` annotations -> `Heading`.
- filename lookup via `node.document.filename` (remove `hasattr(..., "env")`).

#### `src/org/commands/tasks/board.py`
- `OrgNode` annotations -> `Heading`.
- `node.heading` -> `node.title_text`.

#### `src/org/commands/stats/all.py`
- `OrgNode` annotations -> `Heading`.
- `analyze(...)` call updated for removed `category_property` parameter.
- Remove `--category-property` option and arg field.

#### `src/org/commands/stats/summary.py`
- Remove `category_property` from args/options.
- `compute_category_histogram(nodes, args.category_property)` ->
  `compute_category_histogram(nodes)`.

#### `src/org/commands/stats/tags.py`
- Remove `category_property` from args/options.

#### `src/org/commands/stats/groups.py`
- Remove `category_property` from args/options.

### Query runtime

#### `src/org/query_language/runtime.py`
- Replace orgparse imports with `Document`, `Heading`, `Timestamp`, `Clock`, `Repeat`.
- Root collection handling: `OrgRootNode` -> `Document`, `list(root[1:])` -> `list(root)`.
- Date comparisons and parsing migrate from `OrgDate*` to `Timestamp`/`Clock`/`Repeat`.
- Remove empty-orgdate normalization branch; `Timestamp` is always valid.
- Rename `_parse_org_date` -> `_parse_timestamp` and `_as_org_date_or_none` ->
  `_as_timestamp_or_none`.
- Implement helper:

```python
def _timestamp_from_datetimes(
    start: datetime,
    end: datetime | None = None,
    active: bool | None = None,
) -> Timestamp:
    ...
```

- `_func_timestamp`, `_func_clock`, `_func_repeated_task` construct org-parser
  objects directly.

### Config plumbing

#### `src/org/config.py`
- Remove `category_property` from config option maps and defaults handling:
  - `COMMAND_OPTION_NAMES`
  - `DEST_TO_OPTION_NAME`
  - stats `str_options` (`--category-property`)
  - any default-map propagation paths.

---

## Docs and examples updates

### `README.md`
- Update built-in query/filter examples from `.repeated_tasks` to `.repeats`.

### `docs/index.md`
- Update built-in sort examples from `.repeated_tasks` to `.repeats`.

### `docs/query_command.md`
- Update query examples from `.heading` to `.title_text`.

### `docs/query_language.md`
- Update field references (`.heading`, `.body`, `.repeated_tasks`) to new names.
- Update runtime type names in docs (`OrgNode`, `OrgRootNode`, `OrgDate*`) to
  `Heading`, `Document`, `Timestamp`, `Clock`, `Repeat`.
- Explicitly document this as a breaking change.

---

## Test updates (complete list)

### Core fixtures and parsing helpers

#### `tests/conftest.py`
- `orgparse` -> `org_parser`.
- Return type `list[Heading]`.
- `list(root[1:])` -> `list(root)`.

### Filter and timestamp behavior

#### `tests/test_filtered_org_node.py`
- Rewrite for wrapper removal and in-place repeat filtering.
- Update repeat assertions to `.timestamp.start` and `.repeats`.

#### `tests/test_filter_functions.py`
- Import `Heading` instead of `OrgNode`.
- `.repeated_tasks` -> `.repeats`; `.start` on repeats -> `.timestamp.start`.
- Remove/adjust immutability assertions that relied on wrappers.

#### `tests/test_filter_chain.py`
- Replace `orgparse.node.OrgNode` typing with `Heading`.

#### `tests/test_preprocess_tags.py`
- `.heading` -> `.title_text`, `.body` -> `.body_text`.

#### `tests/test_filter_category.py`
- If `filter_category` remains: remove property-name dependency and assert
  category behavior via `node.category` / `title_text`.
- If `filter_category` is removed: delete this test file.

#### `tests/test_extract_timestamp.py`
- Keep behavior assertions; ensure fixtures now provide `Heading` objects.

### Analysis and integration

#### `tests/test_compute_task_state_histogram.py`
- `orgparse.loads` -> `org_parser.loads`; `list(ns[1:])` -> `list(ns)`.

#### `tests/test_analyze.py`
- Remove `orgparse` type references.
- Update `analyze(...)` calls to new signature (no `category_property`).

#### `tests/test_integration.py`
- `orgparse` -> `org_parser`.
- `load_org_file` returns `list[Heading]` via `list(document)`.
- Update `analyze(...)` calls to new signature.

### Query runtime, parser/compiler, command behavior

#### `tests/test_query_language_runtime.py`
- Replace orgparse imports and type assertions with org-parser classes.
- Update query strings to `.title_text`, `.body_text`, `.repeats`.
- Update expected type names from old orgparse names to new class names.

#### `tests/test_query_language_parser.py`
- Update parser fixtures/examples from `.heading`/`.body` to
  `.title_text`/`.body_text`.

#### `tests/test_query_language_compiler.py`
- Update compiler test query literals using renamed fields.

#### `tests/cli_common/test_filter_construction.py`
- Update expected built-in query fragments from `.repeated_tasks` to `.repeats`,
  and heading/body field names.

#### `tests/cli_common/test_top_tasks.py`
- `.heading` assertions -> `.title_text`.

#### `tests/commands/test_query_command.py`
- Update expected JSON `type` strings (`Document` / `Heading` instead of
  `OrgRootNode` / `OrgNode`).

#### `tests/commands/tasks/test_tasks_list.py`
- Update expected JSON `type` strings similarly.

#### `tests/test_output_format.py`
- Fake node casts use `Heading`.
- Update any type-name expectations tied to orgparse classes.

### Stats command tests

#### `tests/commands/stats/test_stats_commands.py`
- Remove `category_property` argument from test helper args.
- Update expectations for removed `--category-property` switch.

#### `tests/commands/tasks/test_tasks_board.py`
#### `tests/commands/tasks/test_tasks_list.py`
- Remove `category_property` field from test arg builders if no longer present.

---

## Implementation order

1. Update plan consumers with locked decisions (this doc).
2. Add `org-parser` dependency (keep `orgparse` temporarily during migration).
3. Migrate `src/org/parse.py` and `tests/conftest.py` first.
4. Migrate `src/org/timestamp.py`, `src/org/filters.py`, `src/org/analyze.py`.
5. Migrate `src/org/cli_common.py` built-in query fragments to new field names.
6. Migrate rendering/export/command files:
   - `src/org/tui.py`
   - `src/org/output_format.py`
   - `src/org/commands/query.py`
   - `src/org/commands/tasks/list.py`
   - `src/org/commands/tasks/board.py`
   - `src/org/commands/stats/all.py`
   - `src/org/commands/stats/summary.py`
   - `src/org/commands/stats/tags.py`
   - `src/org/commands/stats/groups.py`
7. Migrate `src/org/query_language/runtime.py` (date constructors and type checks).
8. Remove `category_property` from `src/org/config.py` and all arg dataclasses/options.
9. Update docs and README examples.
10. Update full test suite listed above.
11. Remove `orgparse` dependency from `pyproject.toml` and regenerate `poetry.lock`.
12. Run `poetry run task check` and fix remaining failures.

---

## Validation checklist

- `poetry run task check` passes.
- No `import orgparse` remains.
- No `OrgNode`/`OrgRootNode`/`OrgDate*` references remain in runtime code.
- No built-in query fragments use `.heading`, `.body`, or `.repeated_tasks`.
- No `category_property` argument/switch/default remains.
- Docs/examples use new field names.
