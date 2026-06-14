# org-cli

`org-cli` is a Python CLI for analyzing Org-Mode archives: query task data, list tasks, and inspect task/tag statistics.

[Documentation](docs/index.md)

## Installation

```bash
poetry install
```

This installs the `org` command.

## Configuration

`org-cli` loads `.org-cli.yaml` from the current directory by default.

Top-level config sections:

- `defaults` for built-in option defaults
- `filter` for custom `--filter-<name>` query snippets
- `order-by` for custom `--order-by-<name>` query snippets
- `with` for custom `--with-<name>` query snippets
- `capture` for named task capture templates
- `agenda` for named agenda views
- `board` for named board views

See [docs/index.md](docs/index.md) for the full config layout.

## Commands

### `tasks`

- `org tasks add` - Create a new task heading and insert it into an Org file.
- `org tasks update` - Update one or more matched task headings and save the changes.
- `org tasks remove` - Delete one or more matched task headings and their subtrees.
- `org tasks capture` - Create a task from a configured capture template.
- `org tasks list` - List matching tasks in interactive, static, or exported form.
- `org tasks query` - Run jq-style queries over loaded Org task data.
  Query language reference: [docs/query_language.md](docs/query_language.md)

### `stats`

- `org stats summary` - Show task-only summary metrics and histograms.
- `org stats tags` - Show statistics for selected tags or top tag results.
- `org stats groups` - Show statistics for explicit or discovered tag groups.
- `org stats all` - Show the combined overview of tasks, tags, and groups.

### `agenda`

- `org agenda` - Show a day-oriented interactive agenda with scheduling and deadline views.

### `board`

- `org board` - Show an interactive board view of tasks using configured or fallback columns.


## Roadmap

- Current roadmap: [VIBES.org](VIBES.org)
