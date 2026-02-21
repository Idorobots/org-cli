# org-cli

Analyze Emacs Org-mode archive files to extract task statistics and tag/word frequencies.

## Installation

```bash
poetry install
```

Installing `org-cli` provides the `org` command.

## Project Structure

```
org-cli/
├── src/
│   └── org/                  # Main package
│       ├── __init__.py       # Package initialization (exports main, version, etc.)
│       ├── __main__.py       # Entry point for `python -m org`
│       ├── cli.py            # CLI interface
│       ├── analyze.py        # Analysis logic
│       └── filters.py        # Filtering utilities
├── tests/                    # Test suite
├── examples/                 # Sample Org-mode archive files
├── pyproject.toml            # Poetry configuration & build settings
└── poetry.lock               # Poetry dependency lock file
```

## Usage

Basic usage:
```bash
poetry run org <org-file> [<org-file> ...]
```

### Common Options

```bash
# Display help
poetry run org --help

# Limit number of results
poetry run org -n 10 examples/ARCHIVE_small

# Filter by task difficulty (requires --with-gamify-category)
poetry run org --with-gamify-category --filter-category simple examples/ARCHIVE_small
poetry run org --with-gamify-category --filter-category regular examples/ARCHIVE_small
poetry run org --with-gamify-category --filter-category hard examples/ARCHIVE_small
poetry run org --with-gamify-category --filter-category all examples/ARCHIVE_small

# Show different data categories
poetry run org --use tags examples/ARCHIVE_small       # Analyze tags (default)
poetry run org --use heading examples/ARCHIVE_small    # Analyze headline words
poetry run org --use body examples/ARCHIVE_small       # Analyze body words

# Use custom exclusion list
poetry run org --exclude stopwords.txt examples/ARCHIVE_small

# Use custom tag mappings
poetry run org --mapping tag_mappings.json examples/ARCHIVE_small

# Filter by date range
poetry run org --filter-date-from 2023-10-01 --filter-date-until 2023-10-31 examples/ARCHIVE_small

# Filter by completion status
poetry run org --filter-completed examples/ARCHIVE_small
poetry run org --filter-not-completed examples/ARCHIVE_small

# Filter by specific tags or properties
poetry run org --filter-tag debugging examples/ARCHIVE_small
poetry run org --filter-property priority=A examples/ARCHIVE_small

# Combine multiple options
poetry run org -n 25 --with-gamify-category --filter-category hard --exclude stopwords.txt examples/ARCHIVE_small
```

### Example Output

```bash
poetry run org examples/ARCHIVE_small
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
- `--max-tags N` - Maximum number of tags to display in Top tags section (default: 5, use 0 to omit section)
- `--max-relations N` - Maximum number of relations to display per item (default: 5, use 0 to omit sections)
- `--max-groups N` - Maximum number of tag groups to display (default: 5, use 0 to omit section)
- `--min-group-size N` - Minimum group size to display (default: 2)
- `--buckets N` - Number of time buckets for timeline charts (default: 50, minimum: 20)
- `--with-gamify-category` - Preprocess nodes to set category property based on gamify_exp value (disabled by default)
- `--with-tags-as-category` - Preprocess nodes to set category property based on first tag (disabled by default)
- `--category-property PROPERTY` - Property name for category histogram and filtering (default: CATEGORY)
- `--filter-category VALUE` - Filter tasks by category property value (e.g., simple, regular, hard, none, or custom). Use 'all' to skip category filtering (default: all)
- `--use CATEGORY` - Category to display: tags, heading, or body (default: tags)
- `--exclude FILE` - File with words to exclude (one word per line, replaces default)
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
