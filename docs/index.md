# org-cli Documentation

`org-cli` is a CLI for exploring Org-mode archives: querying tasks, listing tasks, and generating task/tag statistics.

## Commands

- `org tasks query` - Run jq-style queries over loaded Org data. See [tasks_query_command.md](tasks_query_command.md).
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

## Configuration

- Default config file: `.org-cli.yaml` in the current directory.
- Override config file: `--config FILE`.
- Mapping source: `--mapping FILE` (JSON object: `{"from": "to"}`) or inline config value.
- Exclude source: `--exclude FILE` (one value per line) or inline config list.

### Config file layout

Config uses shared top-level keys plus structured command sections:

- Shared top-level keys: `mapping`, `exclude`, `todo_states`, `done_states`, shared filters, shared ordering flags, `color_flag`, `verbose`, and `with_tags_as_category`.
- `filter`: custom `--filter-<name>` query snippets.
- `order-by`: custom `--order-by-<name>` query snippets.
- `with`: custom `--with-<name>` query snippets.
- `tasks`: tasks subcommand defaults such as `tasks.capture.templates`, `tasks.list`, `tasks.query`, and `tasks.find`.
- `stats`: stats defaults such as `max_results`, `max_tags`, `max_relations`, `min_group_size`, `max_groups`, `use`, `tags`, `groups`.
- `agenda`: agenda defaults and named views under `agenda.views`.
- `board`: board defaults and named views under `board.views`.

Custom switch argument handling:

- If a custom query uses `$arg`, the associated generated switch requires exactly one argument.
- If a custom query does not use `$arg`, the associated generated switch does not require an argument.

Example:

```yaml
done_states: DONE,CANCELLED,DELEGATED
mapping: examples/mapping_example.json
exclude: examples/exclude_example.txt
filter_priority: A
stats:
  max_results: 10
tasks:
  capture:
    templates:
      quick:
        file: tasks.org
        content: "* TODO {{title}}"
  list:
    max_results: 10
    out_theme: github-dark
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

- Shared defaults: `--offset 0`, `--todo-states TODO`, `--done-states DONE`.
- Limit defaults are command-specific: many query/list/stats commands default `--limit` to `10`, while
  `org agenda` and `org board` default to all results.
- Stats: `--use tags`, `--max-tags 5` (all), `--max-relations 5`, `--max-groups 5` (all), `--min-group-size 2` (all).
- Built-in filter additions: `--filter-priority P`.
- Tasks list/board built-in ordering: `--order-by-priority`, `--order-by-level`, `--order-by-file-order`, `--order-by-file-order-reversed`, `--order-by-timestamp-asc`, `--order-by-timestamp-desc`.
- Tasks list default ordering remains timestamp-desc (same as `--order-by-timestamp-desc`).

Repository-local config may override built-ins. In this repository, `.org-cli.yaml` sets:

- `done_states: DONE,CANCELLED`
- `todo_states: TODO,SUSPENDED`
- `mapping: examples/mapping_example.json`
- `exclude: examples/exclude_example.txt`
- `board.view: default`

Common date formats for date filters:

- `YYYY-MM-DD`
- `YYYY-MM-DDThh:mm`
- `YYYY-MM-DDThh:mm:ss`
- `YYYY-MM-DD hh:mm`
- `YYYY-MM-DD hh:mm:ss`

## Categories

`org-cli` can derive categories from tags with `--with-tags-as-category`.
