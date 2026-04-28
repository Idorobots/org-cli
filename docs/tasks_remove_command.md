# `org tasks remove`

Delete one task heading (including its full subtree) from an Org document.

## Usage

```bash
poetry run org tasks remove [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--config FILE` - Config file name to load from current directory (default: `.org-cli.yaml`).
- `--query-title TEXT` - Heading title text of the task to remove.
- `--query-id TEXT` - ID of the task to remove.
- `--query QUERY` - Generic query-language predicate used to select one task.
- `--yes` - Automatically confirm deletion without prompting.
- `--color/--no-color` - Force color behavior for interactive prompt.

## Selector rules

- Provide exactly one selector: `--query-title`, `--query-id`, or `--query`.
- Passing neither selector returns an error.
- Passing multiple selector switches returns an error.
- Blank selector values (for example `--query-title "   "`) return an error.
- `--query` is wrapped as `.[] | select(<QUERY>)` before execution.

## Matching behavior

- Input files are resolved from `[FILE ...]`.
- Matching checks all resolved files.
- The selector can match one or more tasks across all files.
- If no tasks match, command exits with an error.

## Confirmation behavior

- The command shows a `y/n` confirmation prompt with affected task count.
- `--yes` skips the prompt and applies deletion immediately.

## Delete behavior

- Every selected heading is deleted.
- All child headings under each matched heading are removed as part of the same delete.
- After success, the command prints `Deleted {number} tasks.`.

## Examples

1) Delete by title

```bash
poetry run org tasks remove --query-title "Update the docs" ROADMAP.org
```

2) Delete by ID

```bash
poetry run org tasks remove --query-id task-123 ROADMAP.org
```

3) Search multiple files and delete one uniquely matched task

```bash
poetry run org tasks remove --query-title "Refactor parser" notes.org backlog.org
```

4) Delete by generic query selector

```bash
poetry run org tasks remove --query '.title_text == "Test"' ROADMAP.org
```

5) Delete all matching tasks without prompt

```bash
poetry run org tasks remove --query-title "Stale" --yes backlog.org
```
