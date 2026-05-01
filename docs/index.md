# org-cli Documentation

`org-cli` is a CLI for exploring Org-mode archives: querying tasks, listing tasks, and generating task/tag statistics.

## Commands

- `org query` - Run jq-style queries over loaded Org data. See [query_command.md](query_command.md).
- `org agenda` - Day-oriented agenda view with timetable and deadlines. See [agenda_command.md](agenda_command.md).
- `org stats all` - Full stats view (tasks + tags + groups). See [stats_all_command.md](stats_all_command.md).
- `org stats summary` - Task-only stats and histograms. See [stats_summary_command.md](stats_summary_command.md).
- `org stats tags` - Focused stats for selected/top tags. See [stats_tags_command.md](stats_tags_command.md).
- `org stats groups` - Stats for explicit or discovered tag groups. See [stats_groups_command.md](stats_groups_command.md).
- `org tasks list` - Short or detailed task listing with ordering. See [tasks_list_command.md](tasks_list_command.md).
- `org board` - Interactive workflow board view of active tasks. See [board_command.md](board_command.md).
- `org tasks add` - Create new task headings in Org files. See [tasks_add_command.md](tasks_add_command.md).
- `org tasks remove` - Delete one task heading and its subtree from Org files. See [tasks_remove_command.md](tasks_remove_command.md).
- `org tasks update` - Update one matched task heading in Org files. See [tasks_update_command.md](tasks_update_command.md).
- `org tasks capture` - Create tasks from named config templates. See [tasks_capture_command.md](tasks_capture_command.md).

For query syntax details, use [query_language.md](query_language.md).

## Configuration and Defaults

- Default config file: `.org-cli.yaml` in the current directory.
- Override config file: `--config FILE`.
- Mapping source: `--mapping FILE` (JSON object: `{"from": "to"}`) or inline config value.
- Exclude source: `--exclude FILE` (one value per line) or inline config list.

### Config file layout

Config uses five top-level sections:

- `defaults`: built-in option defaults (for example `--done-states`, `--limit`, `--filter-priority`, `--order-by-priority`).
- `filter`: custom `--filter-<name>` query snippets.
- `order-by`: custom `--order-by-<name>` query snippets.
- `with`: custom `--with-<name>` query snippets.
- `capture`: named capture templates under `capture.templates`.

Custom switch argument handling:

- If a custom query uses `$arg`, the associated generated switch requires exactly one argument.
- If a custom query does not use `$arg`, the associated generated switch does not require an argument.

Example:

```yaml
defaults:
  --done-states: DONE,CANCELLED,DELEGATED
  --limit: 10
  --mapping: examples/mapping_example.json
  --exclude: examples/exclude_example.txt
  --filter-priority: A
filter:
  level-above: select(.level > $arg)
  has-todo: select(.todo != null)
order-by:
  recent-first: sort_by(.repeats + .deadline + .closed + .scheduled | max)
with:
  priority-value: .properties.priority_value = .priority
```

Most analysis commands accept many `--filter-*` switches. Ordering controls are available on `org tasks list` and `org board` via built-in `--order-by-*` switches.

Built-in argument defaults:

- Global: `--limit 10`, `--offset 0`, `--todo-states TODO`, `--done-states DONE`.
- Stats: `--use tags`, `--max-tags 5` (all), `--max-relations 5`, `--max-groups 5` (all), `--min-group-size 2` (all).
- Built-in filter additions: `--filter-priority P`.
- Tasks list/board built-in ordering: `--order-by-priority`, `--order-by-level`, `--order-by-file-order`, `--order-by-file-order-reversed`, `--order-by-timestamp-asc`, `--order-by-timestamp-desc`.
- Tasks list default ordering remains timestamp-desc (same as `--order-by-timestamp-desc`).

Repository-local defaults may override built-ins. In this repository, `.org-cli.yaml` sets:

- `--done-states DONE,CANCELLED,DELEGATED`
- `--limit 10`
- `--mapping examples/mapping_example.json`
- `--exclude examples/exclude_example.txt`

Common date formats for date filters:

- `YYYY-MM-DD`
- `YYYY-MM-DDThh:mm`
- `YYYY-MM-DDThh:mm:ss`
- `YYYY-MM-DD hh:mm`
- `YYYY-MM-DD hh:mm:ss`

## Categories

`org-cli` can derive categories from tags with `--with-tags-as-category`.
