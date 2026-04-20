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
- Deadlines on the rendered day with a specific hour are also aligned to hour rows.
- A `NOW` marker is rendered for the current hour when the rendered day is today.
- Within the current hour, `NOW` is placed after tasks at the same minute and before later tasks.
- Inactive planning timestamps (`SCHEDULED`/`DEADLINE` with `[...]`) are omitted.
- Repeat entries are still included even when repeat timestamps are inactive.
- After timed rows, sections are rendered in this order:
  1. Overdue deadlines
  2. Overdue scheduled tasks
  3. Deadlines without specific time (for the rendered day)
  4. Scheduled tasks without specific time
  5. Upcoming deadlines (within 30 days)
- Scheduled tasks without specific time use an empty time cell (no `all day` label).
- Overdue sections are sorted oldest-first.
- Upcoming deadlines are sorted soonest-first and rendered in yellow.
- Overdue/upcoming sections are shown only for the day that matches the actual current date:
  - if `--date` is not today (single-day view), these sections are omitted;
  - if a multi-day span includes today, they appear on that day only.

## Interactive mode

When both stdin and stdout are TTYs, `org agenda` runs in interactive mode.
When not running in a TTY (for example in tests, piping, or redirected output), it falls back
to non-interactive rendering.

Interactive keys:

- Agenda content is rendered in a scrollable top viewport with a fixed footer for controls/status.
- Scrolling follows selection, so repeated `n`/`p`, arrow navigation, or mouse-wheel scrolling moves
  through full content.
- Selection can land on non-task rows (for example empty hour slots) for easier scrolling.
- Task-only actions (`t`, `Shift+Left/Right`, `Shift+Up/Down`, `r`, `c`) show a status
  message when used on non-task rows.
- `n` / `p`, `Up` / `Down`, or mouse wheel - Select next/previous row.
- `f` / `b` or `Right` / `Left` - Move agenda span forward/backward by `--days`.
- `t` - Set TODO state from `heading.document.all_states`.
  - Also appends a repeat/log transition from previous state to new state.
  - If `SCHEDULED` or `DEADLINE` has a repeater marker, it advances one repeater step.
- `Shift+Right` / `Shift+Left` - Shift selected task planning date by plus/minus one day.
  - Deadline-like rows shift `DEADLINE`.
  - Scheduled-like rows shift `SCHEDULED`.
- `Shift+Down` / `Shift+Up` - Shift selected timed scheduled/deadline row by plus/minus one hour.
- `r` - Refile selected task to another file.
  - Prompts with numeric shortcuts for current `FILE` inputs.
- `c` - Add clock entry ending at current time.
  - Prompts for duration (`H:MM`, `Xm`, `Xh`, or minute count).
- `q` or `Esc` - Quit interactive mode.

Unsupported keys do not exit interactive mode; they are shown in the status area.

Every interactive edit is saved immediately and logged through the standard `org` logger.

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
