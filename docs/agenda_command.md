# `org agenda`

Show a day-focused agenda view with scheduled tasks, repeats, overdue items, and upcoming deadlines.

## Usage

```bash
poetry run org agenda [OPTIONS] [FILE ...]
```

## Agenda layout

- Full-width table columns: `CATEGORY`, `TIME`, `TASK`, `TAGS`.
- The `TIME` header displays the rendered day date (`YYYY-MM-DD`).
- Each day in `--days` is rendered as its own table, with its own header.
- The table uses a header/content separator line without vertical grid lines.
- A 24-hour timetable is rendered for each selected day.
- Timed scheduled tasks and completed repeat entries are aligned to hour rows.
- A `NOW` marker is rendered for the current hour when the rendered day is today.
- Within the current hour, `NOW` is placed after tasks at the same minute and before later tasks.
- Inactive planning timestamps (`SCHEDULED`/`DEADLINE` with `[...]`) are omitted.
- Repeat entries are still included even when repeat timestamps are inactive.
- After timed rows, sections are rendered in this order:
  1. Overdue deadlines
  2. Overdue scheduled tasks
  3. Scheduled tasks without specific time
  4. Upcoming deadlines (within 30 days)
- Scheduled tasks without specific time use an empty time cell (no `all day` label).
- Overdue sections are sorted oldest-first.
- Upcoming deadlines are sorted soonest-first and rendered in yellow.
- Overdue/upcoming sections are shown only for the day that matches the actual current date:
  - if `--date` is not today (single-day view), these sections are omitted;
  - if a multi-day span includes today, they appear on that day only.

## Command-specific switches

- `--date DATE` - Start date (`YYYY-MM-DD` or ISO datetime). Defaults to today.
- `--days N` - Number of days to render starting at `--date` (minimum: `1`, default: `1`).
- `--no-completed` - Omit tasks in done states, including completed repeat entries.
- `--no-overdue` - Omit overdue scheduled/deadline sections.
- `--no-upcoming` - Omit upcoming deadline section.
- `--limit`, `-n` - Maximum number of processed tasks (defaults to all results).
- `--offset` - Skip first N processed tasks.
- `--width` - Override console width (minimum: `50`).

## Available filters

- `--filter-priority P` - Keep only tasks with priority equal to `P`.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Available orderings and enrichments

- Ordering switches are the same as `org tasks list` and `org tasks board`:
  `--order-by-priority`, `--order-by-level`, `--order-by-file-order`,
  `--order-by-file-order-reversed`, `--order-by-timestamp-asc`, `--order-by-timestamp-desc`.
- Enrichment: `--with-tags-as-category`.

## Examples

1) Show today

```bash
poetry run org agenda examples/ARCHIVE_small
```

2) Show a specific day without completed tasks

```bash
poetry run org agenda \
  --date 2025-01-15 \
  --no-completed \
  examples/ARCHIVE_small
```

3) Show a 7-day agenda window without overdue items

```bash
poetry run org agenda \
  --date 2025-01-15 \
  --days 7 \
  --no-overdue \
  examples/ARCHIVE_small
```
