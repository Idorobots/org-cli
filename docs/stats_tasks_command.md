# `org stats tasks`

Show task-only statistics and histograms (no tag/group sections).

## Usage

```bash
poetry run org stats tasks [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--category-property` - Property name used for category histogram.
- `--with-gamify-category` - Derive category from `gamify_exp`.
- `--with-tags-as-category` - Derive category from first tag.
- `--with-numeric-gamify-exp` - Normalize `gamify_exp` before category logic.
- `--buckets` - Control timeline/histogram resolution.

## Available filters

- `--filter-gamify-exp-above N`, `--filter-gamify-exp-below N` - Filter by `gamify_exp` thresholds.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Examples

1) Get a task-only status overview

```bash
poetry run org stats tasks examples/ARCHIVE_small
```

2) Analyze tasks completed within a date range

```bash
poetry run org stats tasks \
  --filter-date-from 2023-10-20 \
  --filter-date-until 2023-11-15 \
  --filter-completed \
  examples/ARCHIVE_small
```

3) Split workload by `gamify_exp` difficulty

```bash
poetry run org stats tasks \
  --with-gamify-category \
  examples/ARCHIVE_small
```

4) Group task categories by first tag

```bash
poetry run org stats tasks \
  --category-property CATEGORY \
  --with-tags-as-category \
  examples/ARCHIVE_small
```

5) Build a filtered, category-aware task report

```bash
poetry run org stats tasks \
  --with-gamify-category \
  --category-property CATEGORY \
  --filter-date-from 2023-10-20 \
  --filter-date-until 2023-11-15 \
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

Example full output excerpt (ellided):

```text
Total tasks: 33
Unique tasks: 32
...
Task states:
  DONE     ┊█████████████████████████████████████████████ 30
...
Task categories:
  regular  ┊████████████████████████████ 19
  simple   ┊█████████████████████ 14
```

## How to read plots and histograms

- Frequency plot (top sparkline): timeline of all matched tasks; higher blocks mean busier periods.
- Histograms (`Task states`, `Task priorities`, `Task categories`, `Task occurrence by day of week`): each row is a bucket; bar length is count.
