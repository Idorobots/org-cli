# `org board`

Display active tasks as an interactive workflow board with one column per state.

## Usage

```bash
poetry run org board [OPTIONS] [FILE ...]
```

## Board layout

- Columns are: `NOT STARTED`, each state from `--todo-states`, and final `COMPLETED`.
- Tasks with todo state in `--done-states` are placed in `COMPLETED`.
- Tasks without a todo state are placed in `NOT STARTED`.
- Tasks with unknown states are also placed in `NOT STARTED` so no tasks are hidden.
- Lane contents are ordered by priority: `A`, `B`, `C`, then no priority.

## Interactive mode

When both stdin and stdout are TTYs, `org board` runs in interactive mode.
When not running in a TTY (for example in tests, piping, or redirected output), it falls back
to non-interactive rendering.

Interactive keys:

- Board content is rendered in a scrollable viewport with fixed headers and footer.
- Footer shows `Rows X/Y`, keybindings, and status messages.
- `Up` / `Down` or mouse wheel - Move highlighted task within selected column.
- `Left` / `Right` - Move highlight between columns.
- `Enter` - Open full selected task subtree in syntax-highlighted pager.
- `a` - Capture a new task using standard `org tasks capture` template rules.
- `Shift+Left` / `Shift+Right` - Move selected task to neighboring column by changing state.
  - Moving into coalesced `COMPLETED` prompts for a specific done state.
  - Every state change appends one repeat/logbook transition entry.
- `Shift+Up` / `Shift+Down` - Increase/decrease priority one step (`A`/`B`/`C`/none).
- `q` or `Esc` - Quit interactive mode.

Every interactive edit is saved immediately and logged through the standard `org` logger.

## Command-specific switches

- `--order-by-level` - Sort by heading level (repeatable).
- `--order-by-file-order` - Keep/archive input order (repeatable).
- `--order-by-file-order-reversed` - Reverse archive input order (repeatable).
- `--order-by-priority` - Sort by task priority (repeatable).
- `--order-by-timestamp-asc` - Sort by task timestamp ascending (repeatable).
- `--order-by-timestamp-desc` - Sort by task timestamp descending (repeatable).
- `--limit`, `-n` - Maximum number of results to display (defaults to all results).
- `--offset` - Skip first N results.
- `--width` - Override console width (minimum: `80`).
- `--coalesce-completed/--no-coalesce-completed` - Single `COMPLETED` lane vs one lane per done state.

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
