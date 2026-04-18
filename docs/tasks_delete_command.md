# `org tasks delete`

Delete one task heading (including its full subtree) from an Org document.

## Usage

```bash
poetry run org tasks delete [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--config FILE` - Config file name to load from current directory (default: `.org-cli.json`).
- `--query-title TEXT` - Heading title text of the task to remove.
- `--query-id TEXT` - ID of the task to remove.
- `--query QUERY` - Generic query-language predicate used to select one task.

## Selector rules

- Provide exactly one selector: `--query-title`, `--query-id`, or `--query`.
- Passing neither selector returns an error.
- Passing multiple selector switches returns an error.
- Blank selector values (for example `--query-title "   "`) return an error.
- `--query` is wrapped as `.[] | select(<QUERY>)` before execution.

## Matching behavior

- Input files are resolved from `[FILE ...]`.
- Matching checks all resolved files.
- The selector must match exactly one task across all files.
- If no tasks match, command exits with an error.
- If multiple tasks match, command exits with an error.

## Delete behavior

- The matched heading is removed from its parent.
- All child headings under the matched heading are removed as part of the same delete.

## Examples

1) Delete by title

```bash
poetry run org tasks delete --query-title "Update the docs" ROADMAP.org
```

2) Delete by ID

```bash
poetry run org tasks delete --query-id task-123 ROADMAP.org
```

3) Search multiple files and delete one uniquely matched task

```bash
poetry run org tasks delete --query-title "Refactor parser" notes.org backlog.org
```

4) Delete by generic query selector

```bash
poetry run org tasks delete --query '.title_text == "Test"' ROADMAP.org
```
