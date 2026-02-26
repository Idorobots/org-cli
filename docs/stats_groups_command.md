# `org stats groups`

Show stats for explicit tag groups or automatically discovered groups.

## Usage

```bash
poetry run org stats groups [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--group TAG1,TAG2,...` - Add explicit groups (repeat option for multiple groups).
- `--max-results`, `-n` - Limit rendered groups.
- `--max-relations` - Controls relation depth when auto-discovering groups.
- `--use tags|heading|body` - Choose analysis source.
- `--buckets` - Control timeline resolution.

## Available filters

- `--filter-gamify-exp-above N`, `--filter-gamify-exp-below N` - Filter by `gamify_exp` thresholds.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Examples

1) Discover recurring tag groups automatically

```bash
poetry run org stats groups examples/ARCHIVE_small
```

2) Track two known cross-team groupings

```bash
poetry run org stats groups \
  --group Debugging,Erlang \
  --group ProjectManagement,Jira \
  examples/ARCHIVE_small
```

3) Review unfinished grouped work in a date range

```bash
poetry run org stats groups \
  --filter-date-from 2023-10-20 \
  --filter-date-until 2023-11-15 \
  --filter-not-completed \
  examples/ARCHIVE_small
```

4) Compare explicit groups with tighter output limits

```bash
poetry run org stats groups \
  --group Debugging,Erlang \
  --group ProjectManagement,Jira \
  --max-results 2 \
  --buckets 60 \
  examples/ARCHIVE_small
```

Example frequency plot output (ellided):

```text
2023-10-19                                2023-11-14
┊ ▅   ▅ ▅            ▂                ▂  ▂ ▂     █ ┊ 3 (2023-11-14)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

Example group block output (ellided):

```text
Debugging, Erlang
  Total tasks: 9
...
ProjectManagement, Jira
  Total tasks: 10
```

## How to read frequency plots

- Each group block starts with a timeline sparkline.
- Higher bars represent higher grouped activity.
- The right-side label marks the highest bucket value and date.
