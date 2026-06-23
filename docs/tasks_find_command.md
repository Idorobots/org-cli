# `org tasks find`

Find tasks by exact selectors or full-text search.

## Usage

```bash
poetry run org tasks find [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--query-title TEXT` - Select tasks where title exactly matches `TEXT`.
- `--query-id ID` - Select tasks where `ID` exactly matches `ID`.
- `--query QUERY` - Select tasks with a query-language predicate.
- `--search-text TEXT` - Select tasks whose rendered full text contains `TEXT`.
- `--search-pattern REGEX` - Select tasks whose rendered full text matches `REGEX`.
- `--include-context N` - Include up to `N` parent levels for each matched task.
- `--out` - Output format (`org`, `json`, or any Pandoc writer format).
- `--out-theme` - Pygments syntax-highlighting theme for renderable output formats.
- `--pandoc-args` - Extra arguments forwarded to Pandoc during conversion.

## Configuration

Command-specific defaults live under `tasks.find` in `.org-cli.yaml`.

All available options:

```yaml
tasks:
  find:
    include_context: 0
    out: org
    out_theme: github-dark
    pandoc_args: "--wrap=none"
```

Shared top-level config still applies for `mapping`, `exclude`, `todo_states`, `done_states`, and color behavior.

## Examples

1) Find tasks by exact title

```bash
poetry run org tasks find --query-title "Refactor codebase" examples/ARCHIVE_small
```

2) Search full task text

```bash
poetry run org tasks find --search-text "Feature implementation details" examples/ARCHIVE_small
```

3) Include parent context for matched tasks

```bash
poetry run org tasks find --search-pattern "Jira" --include-context 2 examples/ARCHIVE_small
```
