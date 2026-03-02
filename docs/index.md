# org-cli Documentation

`org-cli` is a CLI for exploring Org-mode archives: querying tasks, listing tasks, and generating task/tag statistics.

## Commands

- `org query` - Run jq-style queries over loaded Org data. See [query_command.md](query_command.md).
- `org stats summary` - Full stats view (tasks + tags + groups). See [stats_summary_command.md](stats_summary_command.md).
- `org stats tasks` - Task-only stats and histograms. See [stats_tasks_command.md](stats_tasks_command.md).
- `org stats tags` - Focused stats for selected/top tags. See [stats_tags_command.md](stats_tags_command.md).
- `org stats groups` - Stats for explicit or discovered tag groups. See [stats_groups_command.md](stats_groups_command.md).
- `org tasks list` - Short or detailed task listing with ordering. See [tasks_list_command.md](tasks_list_command.md).

For query syntax details, use [query_language.md](query_language.md).

## Configuration and Defaults

- Default config file: `.org-cli.json` in the current directory.
- Override config file: `--config FILE`.
- Mapping source: `--mapping FILE` (JSON object: `{"from": "to"}`) or inline config value.
- Exclude source: `--exclude FILE` (one value per line) or inline config list.

### Config file layout

Config uses four top-level sections:

- `defaults`: built-in option defaults (for example `--done-keys`, `--buckets`, `--filter-priority`, `--order-by-priority`).
- `filter`: custom `--filter-<name>` query snippets.
- `order-by`: custom `--order-by-<name>` query snippets.
- `with`: custom `--with-<name>` query snippets.

Custom switch argument handling:

- If a custom query uses `$arg`, the associated generated switch requires exactly one argument.
- If a custom query does not use `$arg`, the associated generated switch does not require an argument.

Example:

```json
{
  "defaults": {
    "--done-keys": "DONE,CANCELLED,DELEGATED",
    "--buckets": 80,
    "--mapping": "examples/mapping_example.json",
    "--exclude": "examples/exclude_example.txt",
    "--filter-priority": "A"
  },
  "filter": {
    "level-above": "select(.level > $arg)",
    "has-todo": "select(.todo != none)"
  },
  "order-by": {
    "recent-first": "sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max)"
  },
  "with": {
    "priority-value": ".properties.priority_value = .priority"
  }
}
```

Most analysis commands accept many `--filter-*` switches. Ordering controls are available on `org tasks list` via built-in `--order-by-*` switches.

Built-in argument defaults:

- Global: `--max-results 10`, `--offset 0`, `--todo-keys TODO`, `--done-keys DONE`.
- Stats: `--use tags`, `--max-tags 5` (summary), `--max-relations 5`, `--max-groups 5` (summary), `--min-group-size 2` (summary), `--buckets 50`.
- Built-in filter additions: `--filter-priority P`.
- Tasks list built-in ordering: `--order-by-priority`, `--order-by-level`, `--order-by-file-order`, `--order-by-file-order-reversed`, `--order-by-timestamp-asc`, `--order-by-timestamp-desc`.
- Tasks list default ordering remains timestamp-desc (same as `--order-by-timestamp-desc`).

Repository-local defaults may override built-ins. In this repository, `.org-cli.json` sets:

- `--done-keys DONE,CANCELLED,DELEGATED`
- `--buckets 80`
- `--mapping examples/mapping_example.json`
- `--exclude examples/exclude_example.txt`

Common date formats for date filters:

- `YYYY-MM-DD`
- `YYYY-MM-DDThh:mm`
- `YYYY-MM-DDThh:mm:ss`
- `YYYY-MM-DD hh:mm`
- `YYYY-MM-DD hh:mm:ss`

## Categories

`org-cli` can derive categories from tags with `--with-tags-as-category` and store them in a
customizable property name via `--category-property`.
