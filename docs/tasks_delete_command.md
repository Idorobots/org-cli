# `org tasks delete`

Delete one task heading (including its full subtree) from an Org document.

## Usage

```bash
poetry run org tasks delete [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--config FILE` - Config file name to load from current directory (default: `.org-cli.json`).
- `--title TEXT` - Heading title text of the task to remove.
- `--id TEXT` - ID of the task to remove.

## Selector rules

- Provide exactly one selector: `--title` or `--id`.
- Passing neither selector returns an error.
- Passing both selectors returns an error.
- Blank selector values (for example `--title "   "`) return an error.

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
poetry run org tasks delete --title "Update the docs" ROADMAP.org
```

2) Delete by ID

```bash
poetry run org tasks delete --id task-123 ROADMAP.org
```

3) Search multiple files and delete one uniquely matched task

```bash
poetry run org tasks delete --title "Refactor parser" notes.org backlog.org
```
