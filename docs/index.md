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

Most analysis commands accept many `--filter-*` switches. Ordering controls are available on `org tasks list` via `--order-by`.

Built-in argument defaults:

- Global: `--max-results 10`, `--offset 0`, `--todo-keys TODO`, `--done-keys DONE`.
- Stats: `--use tags`, `--max-tags 5` (summary), `--max-relations 5`, `--max-groups 5` (summary), `--min-group-size 2` (summary), `--buckets 50`.
- Tasks list ordering: default `--order-by timestamp-desc`.

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

## gamify_exp

`org-cli` can read `gamify_exp` and derive categories with `--with-gamify-category`:

- `simple`: `gamify_exp < 10`
- `regular`: `10 <= gamify_exp < 20`
- `hard`: `gamify_exp >= 20`

Tasks with missing or invalid `gamify_exp` are treated as `regular`.

Background on the property source: [gamify-el](https://github.com/Idorobots/gamify-el).
