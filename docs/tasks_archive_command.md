# `org tasks archive`

Archive matched task headings and their full subtrees.

## Usage

```bash
poetry run org tasks archive [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--query-title TEXT` - Heading title text of the task to archive.
- `--query-id TEXT` - `ID` of the task to archive.
- `--query QUERY` - Generic query-language selector expression.

## Configuration

`org tasks archive` has no dedicated command-specific config section.

It only uses shared top-level config such as:

```yaml
todo_states: TODO,WAITING
done_states: DONE,CANCELLED
mapping: examples/mapping_example.json
exclude: examples/exclude_example.txt
color_flag: true
```

## Selector rules

- Provide exactly one selector: `--query-title`, `--query-id`, or `--query`.
- Passing neither selector returns an error.
- Passing multiple selector switches returns an error.
- `--query` is wrapped as `.[] | select(<QUERY>)` before execution.

## Examples

1) Archive by title

```bash
poetry run org tasks archive --query-title "Update the docs" ROADMAP.org
```

2) Archive by ID

```bash
poetry run org tasks archive --query-id task-123 ROADMAP.org
```
