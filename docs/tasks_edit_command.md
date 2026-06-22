# `org tasks edit`

Edit one matched task subtree in an external editor.

## Usage

```bash
poetry run org tasks edit [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--query-title TEXT` - Heading title text of the task to edit.
- `--query-id TEXT` - `ID` of the task to edit.
- `--query QUERY` - Generic query-language selector expression.

## Configuration

`org tasks edit` has no dedicated command-specific config section.

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
- Matching must resolve to exactly one task.
- `--query` is wrapped as `.[] | select(<QUERY>)` before execution.

## Examples

1) Edit by title

```bash
poetry run org tasks edit --query-title "Update the docs" ROADMAP.org
```

2) Edit by ID

```bash
poetry run org tasks edit --query-id task-123 ROADMAP.org
```
