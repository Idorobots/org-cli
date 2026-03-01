# org-cli

`org-cli` is a Python CLI for analyzing Org-Mode archives: query task data, list tasks, and inspect task/tag statistics.

[Documentation](docs/index.md)

## Installation

```bash
poetry install
```

This installs the `org` command.

## Configuration

`org-cli` loads `.org-cli.json` from the current directory by default.

Top-level config sections:

- `defaults` for built-in option defaults
- `filter` for custom `--filter-<name>` query snippets
- `order-by` for custom `--order-by-<name>` query snippets
- `with` for custom `--with-<name>` query snippets

```json
{
  "defaults": {
    "--done-keys": "DONE,CANCELLED,DELEGATED",
    "--buckets": 80,
    "--filter-priority": "A",
    "--mapping": "examples/mapping_example.json",
    "--exclude": "examples/exclude_example.txt"
  },
  "filter": {
    "level-above": "select(.level > $arg)",
    "has-todo": "select(.todo != none)"
  },
  "order-by": {
    "recent-first": "sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max)"
  },
  "with": {
    "priority-value": ". + {\"priority_value\": .priority }"
  }
}
```

## Commands

### `org query`

Run jq-style queries over your Org Mode tasks.

```bash
# Expand all nodes, select completed tasks, extract heading, return a page of results
poetry run org query '[ .[][] | select(.todo in $done_keys) | .heading ][$offset: $offset + $limit]' \
  --done-keys DONE,CANCELLED \
  --max-results 10 \
  --offset 10 \
  examples/ARCHIVE_small
```

```text
Fix broken data endpoint in spartan sensor mesh on ESP8266 when there's too large JSON to stringify.
Replace the humidity/temperature sensors on the inside sensor with CO sensor.
...
```

Query language reference: [docs/query_language.md](docs/query_language.md)

### `org stats summary`

Show a full overview: global task stats, top tasks, top tags, and groups.

```bash
poetry run org stats summary \
  --use tags \
  --max-results 5 \
  --max-tags 3 \
  --max-groups 2 \
  --max-relations 3 \
  examples/ARCHIVE_small
```

```text
2023-10-19                                                              2023-11-14
┊▂ ▂     ▂  ▂     ▆  █        ▄  ▄        ▂              ▄  █  ▄  ▄  ▂     ▄  █  ┊ 4 (2023-10-26)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
Total tasks: 33
Unique tasks: 32
Average tasks per day: 1.22
Max tasks on a single day: 4
Max repeats of a single task: 2

Task states:
  DONE     ┊████████████████████████████████████████████████████████████████████████ 30
  CANCELLED┊██ 1
  DELEGATED┊ 0
  TODO     ┊██ 1
  SUSPENDED┊██ 1
...
```

### `org stats tasks`

Show task-only metrics and histograms.

```bash
poetry run org stats tasks \
  --category-property CATEGORY \
  --with-tags-as-category \
  --filter-date-from 2023-10-20 \
  --filter-date-until 2023-11-15 \
  examples/ARCHIVE_small
```

### `org stats tags`

Show focused stats for selected tags or top tags.

```bash
poetry run org stats tags \
  --show Debugging,Jira \
  --max-relations 3 \
  --filter-not-completed \
  examples/ARCHIVE_small
```

### `org stats groups`

Show stats for explicit or discovered tag groups.

```bash
poetry run org stats groups \
  --group Debugging,Erlang \
  --group ProjectManagement,Jira \
  --max-results 2 \
  examples/ARCHIVE_small
```

### `org tasks list`

List matching tasks with filters and ordering.

```bash
poetry run org tasks list \
  --filter-completed \
  --order-by-level \
  --order-by-timestamp-asc \
  --max-results 5 \
  --offset 20 \
  examples/ARCHIVE_small
```

```text
examples/ARCHIVE_small: * DONE Prepare some stories for refinement.         :Jira:ProjectManagement:
examples/ARCHIVE_small: * DONE Reorganize tickets on the CHAT project board.:Jira:ProjectManagement:
...
```

## Notes

- Command docs and defaults: [docs/index.md](docs/index.md)
- Current roadmap: [VIBES.org](VIBES.org)
