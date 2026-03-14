# `org tasks board`

Display active tasks as a workflow board with one column per todo state.

## Usage

```bash
poetry run org tasks board [OPTIONS] [FILE ...]
```

## Board layout

- Columns are: `NOT STARTED`, each state from `--todo-keys`, and final `COMPLETED`.
- Tasks with todo state in `--done-keys` are placed in `COMPLETED`.
- Tasks without a todo state are placed in `NOT STARTED`.
- Tasks with unknown states are also placed in `NOT STARTED` so no tasks are hidden.
- Task order is preserved from the processed list after enrichments, filters, and ordering.

## Command-specific switches

- `--order-by-level` - Sort by heading level (repeatable).
- `--order-by-file-order` - Keep/archive input order (repeatable).
- `--order-by-file-order-reversed` - Reverse archive input order (repeatable).
- `--order-by-priority` - Sort by task priority (repeatable).
- `--order-by-timestamp-asc` - Sort by task timestamp ascending (repeatable).
- `--order-by-timestamp-desc` - Sort by task timestamp descending (repeatable).
- `--width` - Override console width (minimum: `80`).

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
- `--category-property PROPERTY` - Category property used by enrichment/filter pipeline.

## Examples

1) Show all tasks as a board

```bash
poetry run org tasks board examples/ARCHIVE_small
```

2) Show unfinished tasks ordered by priority and timestamp

```bash
poetry run org tasks board \
  --filter-not-completed \
  --order-by-priority \
  --order-by-timestamp-asc \
  examples/ARCHIVE_small
```

3) Use custom workflow states

```bash
poetry run org tasks board \
  --todo-keys TODO,WAITING,INPROGRESS \
  --done-keys DONE,CANCELLED \
  examples/ARCHIVE_small
```

## Output

- The command always renders a Rich board layout (no `--out` format selection).
- Empty result set prints `No results`.
