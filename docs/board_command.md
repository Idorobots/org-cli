# `org board`

Display tasks on an interactive board.

## Usage

```bash
poetry run org board [OPTIONS] [FILE ...]
```

## Board layout

- Board columns are driven by filters from a configured board view.
- Filters run independently over the full processed task list (after normal filtering/ordering/limit/offset pipeline).
- A task may appear in multiple columns if it matches multiple filters.
- A task that matches no filters is not shown.

When no view is selected (explicitly or via defaults), `org board` uses the built-in fallback view:

- `Backlog` => `.todo == null`
- `TODO` => `.todo != null and not(.is_completed)`
- `DONE` => `.is_completed`

Configured views live under `board.views` in `.org-cli.yaml`.

Example:

```yaml
board:
  views:
    - name: kanban
      columns:
        - name: Backlog
          filter: ".todo == null"
        - name: TODO
          filter: ".todo == \"TODO\""
          order-by: ".priority"
        - name: In progress
          filter: "all([.todo != null, .todo != \"TODO\", not(.is_completed)])"
        - name: "[bold green]Complete[/]"
          filter: ".is_completed"
```

`order-by` is optional per column. When present, it is applied as `sort_by(<order-by>)` after
`filter` selection for that column, overriding the incoming processed order for that column only.
When omitted, column results keep the processed order from the main board pipeline.

## Interactive mode

When both stdin and stdout are TTYs, `org board` runs in interactive mode.
When not running in a TTY (for example in tests, piping, or redirected output), it falls back
to non-interactive rendering.

Interactive keys:

- Board content is rendered in a scrollable viewport with fixed headers and footer.
- Footer shows `Rows X/Y`, keybindings, and status messages.
- `Up` / `Down` or mouse wheel - Move highlighted task within selected column.
- `Left` / `Right` - Move highlight between columns (visual navigation only).
- `Enter` - Open full selected task subtree in syntax-highlighted pager.
- `a` - Capture a new task using standard `org tasks capture` template rules.
- `Shift+Left` / `Shift+Right` - Step selected task state through document state order.
- `Shift+Up` / `Shift+Down` - Increase/decrease priority one step (`A`/`B`/`C`/none).
- `q` or `Esc` - Quit interactive mode.

Every interactive edit is saved immediately and logged through the standard `org` logger.

## Command-specific switches

- `--view NAME` - Select configured board view by name.
- `--order-by-level` - Sort by heading level (repeatable).
- `--order-by-file-order` - Keep/archive input order (repeatable).
- `--order-by-file-order-reversed` - Reverse archive input order (repeatable).
- `--order-by-priority` - Sort by task priority (repeatable).
- `--order-by-timestamp-asc` - Sort by task timestamp ascending (repeatable).
- `--order-by-timestamp-desc` - Sort by task timestamp descending (repeatable).
- `--limit`, `-n` - Maximum number of results to display (defaults to all results).
- `--offset` - Skip first N results.
- `--width` - Override console width (minimum: `80`).

View selection behavior:

- If `--view` is set, that configured view must exist.
- If `--view` is set but no board views are configured, the command fails with an explicit error.
- If `--view` is omitted, config defaults may provide `defaults: --view: <name>`.
- If neither explicit nor default view is set, fallback columns are used.

Filter errors:

- Invalid filter/order-by parse/runtime errors are reported with context including
  `view=<name>, column=<name>`.

## Available filters

- `--filter-priority P` - Keep only tasks with priority equal to `P`.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Available enrichments

- `--with-tags-as-category` - Preprocess nodes by copying first tag into category property.

## Examples

1) Show all tasks as a board

```bash
poetry run org board examples/ARCHIVE_small
```

2) Show unfinished tasks ordered by priority and timestamp

```bash
poetry run org board \
  --filter-not-completed \
  --order-by-priority \
  --order-by-timestamp-asc \
  examples/ARCHIVE_small
```

3) Use custom workflow states

```bash
poetry run org board \
  --todo-states TODO,WAITING,INPROGRESS \
  --done-states DONE,CANCELLED \
  examples/ARCHIVE_small
```

## Output

- The command always renders a Rich board layout (no `--out` format selection).
- In non-interactive mode, when rendered board height exceeds the viewport, output is shown in a pager.
- Empty result set prints `No results`.
