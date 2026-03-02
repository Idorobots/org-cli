# `org stats summary`

Show a compact full report: task-level stats, top tasks, top tags, and tag groups.

## Usage

```bash
poetry run org stats summary [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--use tags|heading|body` - Choose analysis target for tag sections.
- `--max-tags` - Limit TAGS section items (`0` hides section).
- `--max-groups` - Limit GROUPS section items (`0` hides section).
- `--min-group-size` - Skip small groups.
- `--max-relations` - Limit relation entries per item.
- `--buckets` - Control timeline/histogram resolution.
- `--with-tags-as-category`, `--category-property` - Control category derivation.

## Available filters

- `--filter-priority P` - Keep only tasks with priority equal to `P`.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Examples

1) Get a quick project health snapshot

```bash
poetry run org stats summary examples/ARCHIVE_small
```

2) Get a compact summary for dashboards or reports

```bash
poetry run org stats summary \
  --max-results 3 \
  --max-tags 2 \
  --max-groups 1 \
  examples/ARCHIVE_small
```

3) Analyze heading vocabulary trends

```bash
poetry run org stats summary \
  --use heading \
  --max-tags 5 \
  --max-relations 2 \
  examples/ARCHIVE_small
```

4) Review unfinished work in a date window

```bash
poetry run org stats summary \
  --filter-date-from 2023-10-20 \
  --filter-date-until 2023-11-15 \
  --filter-not-completed \
  examples/ARCHIVE_small
```

5) Build a focused summary with tuned section sizes

```bash
poetry run org stats summary \
  --use tags \
  --max-results 5 \
  --max-tags 3 \
  --max-groups 2 \
  --max-relations 3 \
  examples/ARCHIVE_small
```

Example frequency plot output (ellided):

```text
2023-10-19                                2023-11-14
┊▂▂   ▂ ▂   ▆█     ▄ ▄    ▂         ▄ █▄ ▄ ▂   ▄ █ ┊ 4 (2023-10-26)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

Example histogram output (ellided):

```text
Task states:
  DONE     ┊█████████████████████████████████████████████ 30
  TODO     ┊█ 1
  SUSPENDED┊█ 1
```

Example section output (ellided):

```text
Total tasks: 33
Unique tasks: 32
...
TASKS
  examples/ARCHIVE_small: * DONE ...

TAGS
  ProjectManagement
    Total tasks: 10
...
GROUPS
  ProjectManagement, Jira
    Total tasks: 10
```

## How to read plots and histograms

- Frequency plot (sparkline): left is earliest date, right is latest date; taller blocks mean higher activity; right label shows peak count/date.
- Histogram rows: label is the bucket/category, bar length is count.
