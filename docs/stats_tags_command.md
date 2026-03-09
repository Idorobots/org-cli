# `org stats tags`

Show detailed stats for selected tags, or top tags by frequency.

## Usage

```bash
poetry run org stats tags [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--tag TAG` - Show explicit tags (repeat option for multiple tags).
- `--use tags|heading|body` - Choose analysis source.
- `--max-relations` - Limit relation entries per tag.
- `--limit`, `-n` - Limit how many tags are rendered.

## Available filters

- `--filter-priority P` - Keep only tasks with priority equal to `P`.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Examples

1) Find the most frequent tags across your archive

```bash
poetry run org stats tags examples/ARCHIVE_small
```

2) Inspect specific tags you care about

```bash
poetry run org stats tags \
  --tag Debugging \
  --tag Jira \
  examples/ARCHIVE_small
```

3) Analyze frequent heading words instead of tags

```bash
poetry run org stats tags \
  --use heading \
  --limit 5 \
  --max-relations 2 \
  examples/ARCHIVE_small
```

4) Focus tag stats on unfinished tasks

```bash
poetry run org stats tags \
  --tag Debugging \
  --tag Jira \
  --max-relations 3 \
  --filter-not-completed \
  examples/ARCHIVE_small
```

Example frequency plot output (ellided):

```text
2023-10-19                                2023-11-14
┊ █   █ █            █                █  █ █     █ ┊ 1 (2023-10-20)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

Example tag block output (ellided):

```text
Debugging
  Total tasks: 8
  Top relations:
    Erlang (4)
...
Jira
  Total tasks: 6
```

## How to read frequency plots

- The sparkline above each tag is a time distribution for that tag.
- Left/right bounds are earliest/latest dates in scope.
- Taller bars mean more occurrences in that bucket.
