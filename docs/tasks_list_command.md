# `org tasks list`

List tasks as short one-line entries or full Org blocks.

## Usage

```bash
poetry run org tasks list [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--details` - Print full Org node blocks instead of one-line entries.
- `--order-by` - Apply one or more orderings (`file-order`, `file-order-reversed`, `level`, `timestamp-asc`, `timestamp-desc`, `gamify-exp-asc`, `gamify-exp-desc`).
- `--offset` - Skip first N results.
- `--max-results`, `-n` - Limit displayed tasks.
- `--out` - Output format (`org`, `json`, or any Pandoc writer format such as `gfm`, `html5`, `rst`, `pdf`).
- `--out-theme` - Pygments syntax-highlighting theme for renderable output formats (default: `github-dark`).
- `--pandoc-args` - Extra arguments forwarded to Pandoc during conversion.

## Available filters

- `--filter-gamify-exp-above N`, `--filter-gamify-exp-below N` - Filter by `gamify_exp` thresholds.
- `--filter-level N` - Keep only tasks at heading level `N`.
- `--filter-repeats-above N`, `--filter-repeats-below N` - Filter by repeat count.
- `--filter-date-from TS`, `--filter-date-until TS` - Keep tasks in a timestamp window.
- `--filter-property KEY=VALUE` - Exact property match (repeatable).
- `--filter-tag REGEX`, `--filter-heading REGEX`, `--filter-body REGEX` - Regex filters (repeatable).
- `--filter-completed`, `--filter-not-completed` - Filter by completion state.

## Available orderings

- `file-order`, `file-order-reversed` - Keep/archive input order.
- `level` - Sort by heading level.
- `timestamp-asc`, `timestamp-desc` - Sort by task timestamps.
- `gamify-exp-asc`, `gamify-exp-desc` - Sort by `gamify_exp` value.

`--order-by` is repeatable; orderings are applied in the sequence you pass them.

## Examples

1) Fetch the latest tasks quickly

```bash
poetry run org tasks list examples/ARCHIVE_small
```

2) Fetch all tasks that are not completed yet

```bash
poetry run org tasks list --filter-not-completed examples/ARCHIVE_small
```

3) Fetch unfinished tasks ordered by level then time

```bash
poetry run org tasks list \
  --filter-not-completed \
  --order-by level \
  --order-by timestamp-asc \
  --max-results 5 \
  examples/ARCHIVE_small
```

4) Fetch completed tasks for a specific day window with paging

```bash
poetry run org tasks list \
  --filter-completed \
  --filter-date-from 2023-11-01 \
  --filter-date-until 2023-11-01 \
  --order-by level \
  --order-by timestamp-asc \
  --max-results 5 \
  --offset 20 \
  examples/ARCHIVE_small
```

5) Fetch full Org blocks for manual review

```bash
poetry run org tasks list --details --max-results 2 examples/ARCHIVE_small
```

Example output (ellided):

```text
examples/ARCHIVE_small: * DONE Prepare some stories for :Jira:ProjectManagement:
examples/ARCHIVE_small: * DONE Reorganize tickets on the:Jira:ProjectManagement:
...
```

Detailed output example (ellided):

```text
# examples/ARCHIVE_small
* DONE Design a bead for the clothe:3DModeling:OpenSCAD:
...
```

## Output

- Default mode: one task per line with source file prefix.
- `--details` mode: full syntax-highlighted Org blocks.
- Empty result set prints `No results`.

## Output formatting

- `--out` is passed directly to Pandoc (`-t <format>`) for format conversion.
- For renderable text outputs, syntax highlighting uses Rich + Pygments with the theme selected by `--out-theme`.
- Format-to-highlighter mapping is best-effort (`gfm -> markdown`, `html5 -> html`, etc.); unmapped formats are still exported without syntax highlighting.
- Binary Pandoc outputs (for example `--out pdf`) are written as raw bytes (no escaping/formatting), which supports shell redirection.

6) Export as HTML with a selected Pygments theme

```bash
poetry run org tasks list \
  --out html5 \
  --out-theme Vim \
  examples/ARCHIVE_small
```

7) Export PDF by piping raw binary output to a file

```bash
poetry run org tasks list --out pdf examples/ARCHIVE_small > tasks.pdf
```
