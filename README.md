# orgstats

Analyze Emacs Org-mode archive files to extract task statistics and tag/word frequencies.

## Installation

```bash
poetry install
```

## Usage

Basic usage:
```bash
poetry run orgstats <org-file> [<org-file> ...]
```

### Common Options

```bash
# Display help
poetry run orgstats --help

# Limit number of results
poetry run orgstats -n 10 examples/ARCHIVE_small

# Filter by task difficulty
poetry run orgstats --filter simple examples/ARCHIVE_small   # Simple tasks (gamify_exp < 10)
poetry run orgstats --filter regular examples/ARCHIVE_small  # Regular tasks (10 ≤ exp < 20)
poetry run orgstats --filter hard examples/ARCHIVE_small     # Hard tasks (exp ≥ 20)
poetry run orgstats --filter all examples/ARCHIVE_small      # All tasks (default)

# Show different data categories
poetry run orgstats --use tags examples/ARCHIVE_small       # Analyze tags (default)
poetry run orgstats --use heading examples/ARCHIVE_small    # Analyze headline words
poetry run orgstats --use body examples/ARCHIVE_small       # Analyze body words

# Use custom exclusion list
poetry run orgstats --exclude stopwords.txt examples/ARCHIVE_small

# Use custom tag mappings
poetry run orgstats --mapping tag_mappings.json examples/ARCHIVE_small

# Filter by date range
poetry run orgstats --filter-date-from 2023-10-01 --filter-date-until 2023-10-31 examples/ARCHIVE_small

# Filter by completion status
poetry run orgstats --filter-completed examples/ARCHIVE_small
poetry run orgstats --filter-not-completed examples/ARCHIVE_small

# Filter by specific tags or properties
poetry run orgstats --filter-tag debugging examples/ARCHIVE_small
poetry run orgstats --filter-property priority=A examples/ARCHIVE_small

# Combine multiple options
poetry run orgstats -n 25 --filter hard --exclude stopwords.txt examples/ARCHIVE_small
```

### Example Output

```bash
poetry run orgstats examples/ARCHIVE_small
```

```
Processing examples/ARCHIVE_small...

2023-10-22                                2023-11-14
┊▂ ▂   ▆ █     ▄ ▄     ▂          ▄ █ ▄ ▄ ▂   ▄ ▆  ┊ 4 (2023-10-26)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
Total tasks: 33
Average tasks completed per day: 1.25
Max tasks completed on a single day: 4
Max repeats of a single task: 2

Task states:
  DONE     ┊█████████████████████████████████████████████ 30
  TODO     ┊█ 1
  CANCELLED┊█ 1
  SUSPENDED┊█ 1

Task completion by day of week:
  Monday   ┊████████ 5
  Tuesday  ┊████████ 5
  Wednesday┊███████████ 7
  Thursday ┊███████████ 7
  Friday   ┊███ 2
  Saturday ┊█ 1
  Sunday   ┊█████ 3

Top tags:
  2023-10-25                                2023-11-13
  ┊█ █                                █ █         ▄  ┊ 2 (2023-10-25)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  ProjectManagement (9)
    Top relations:
      Jira (6)

  2023-10-22                                2023-11-14
  ┊█ █             █                  █   █ █     █  ┊ 1 (2023-10-22)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  Debugging (7)
    Top relations:
      Erlang (3)
      Electronics (2)
      Arduino (1)

  2023-10-25                                2023-11-13
  ┊▄ ▄                                ▄ █         ▄  ┊ 2 (2023-11-09)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  Jira (6)
    Top relations:
      ProjectManagement (6)

  ...

Tag groups:
  2023-10-22                                2023-11-14
  ┊▃ ▃           ▃ █                  ▁   ▃ ▃     ▆  ┊ 5 (2023-10-30)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  Arduino, Cpp, Debugging, Electronics, Erlang, Redis, Soldering

  2023-10-26                                2023-11-13
  ┊█                                              █  ┊ 2 (2023-10-26)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  AWS, GitHub, Terraform
```

### Available Options

- `--max-results N`, `-n N` - Maximum number of results to display (default: 10)
- `--max-relations N` - Maximum number of relations to display per item (default: 3, must be >= 1)
- `--min-group-size N` - Minimum group size to display (default: 3)
- `--buckets N` - Number of time buckets for timeline charts (default: 50, minimum: 20)
- `--filter TYPE`, `-f TYPE` - Filter tasks by difficulty: `simple`, `regular`, `hard`, or `all` (default: `all`)
- `--use CATEGORY` - Category to display: `tags`, `heading`, or `body` (default: `tags`)
- `--exclude FILE` - File with words to exclude (one per line, replaces default)
- `--mapping FILE` - JSON file containing tag mappings (dict[str, str])
- `--todo-keys KEYS` - Comma-separated list of incomplete task states (default: TODO)
- `--done-keys KEYS` - Comma-separated list of completed task states (default: DONE)
- `--filter-gamify-exp-above N` - Filter tasks where gamify_exp > N (non-inclusive, missing defaults to 10)
- `--filter-gamify-exp-below N` - Filter tasks where gamify_exp < N (non-inclusive, missing defaults to 10)
- `--filter-repeats-above N` - Filter tasks where repeat count > N (non-inclusive)
- `--filter-repeats-below N` - Filter tasks where repeat count < N (non-inclusive)
- `--filter-date-from TIMESTAMP` - Filter tasks with timestamps after date (inclusive)
- `--filter-date-until TIMESTAMP` - Filter tasks with timestamps before date (inclusive)
- `--filter-property KEY=VALUE` - Filter tasks with exact property match (case-sensitive, can specify multiple)
- `--filter-tag REGEX` - Filter tasks where any tag matches regex (case-sensitive, can specify multiple)
- `--filter-heading REGEX` - Filter tasks where heading matches regex (case-sensitive, can specify multiple)
- `--filter-body REGEX` - Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)
- `--filter-completed` - Filter tasks with todo state in done keys
- `--filter-not-completed` - Filter tasks with todo state in todo keys

Date formats: `YYYY-MM-DD`, `YYYY-MM-DDThh:mm`, `YYYY-MM-DDThh:mm:ss`, `YYYY-MM-DD hh:mm`, `YYYY-MM-DD hh:mm:ss`

### Task Difficulty Levels

Tasks are classified based on their `gamify_exp` property:
- **Simple**: `gamify_exp < 10`
- **Regular**: `10 ≤ gamify_exp < 20`
- **Hard**: `gamify_exp ≥ 20`

Tasks without `gamify_exp` or with invalid values default to regular difficulty.

For more details see [gamify-el](https://github.com/Idorobots/gamify-el).

## Testing

```bash
poetry run task check
```
