# orgstats

Analyze Emacs Org-mode archive files to extract task statistics and tag/word frequencies.

## Installation

```bash
poetry install
```

## Usage

Basic usage:
```bash
orgstats <org-file> [<org-file> ...]
```

### Options

```bash
# Display help
orgstats --help

# Limit number of results
orgstats -n 10 examples/ARCHIVE_small

# Filter by task difficulty (filters by selected type)
orgstats --filter simple examples/ARCHIVE_small   # Simple tasks (gamify_exp < 10)
orgstats --filter regular examples/ARCHIVE_small  # Regular tasks (10 ≤ exp < 20)
orgstats --filter hard examples/ARCHIVE_small     # Hard tasks (exp ≥ 20)
orgstats --filter all examples/ARCHIVE_small      # All tasks (default)

# Use custom exclusion list
orgstats --exclude-tags tags.txt examples/ARCHIVE_small
orgstats --exclude-heading heading.txt examples/ARCHIVE_small
orgstats --exclude-body body.txt examples/ARCHIVE_small

# Combine options
orgstats --filter hard -n 10 --exclude-tags tags.txt examples/ARCHIVE_small
```

### Example Output

```bash
orgstats --filter all examples/ARCHIVE_small
```

```
Processing examples/ARCHIVE_small...

Total tasks:  33

Done tasks:  33

Top tags:
  projectmanagement: count=10, earliest=2023-10-19, latest=2023-11-13, top_day=2023-10-25 (2)
    jira (6)
  debugging: count=8, earliest=2023-10-20, latest=2023-11-14, top_day=2023-10-23 (2)
    erlang (4)
    electronics (2)
    xmpp (1)
  jira: count=6, earliest=2023-10-25, latest=2023-11-13, top_day=2023-11-09 (2)
    projectmanagement (6)
  erlang: count=5, earliest=2023-10-20, latest=2023-11-14, top_day=2023-10-23 (2)
    debugging (4)
    xmpp (1)
    redis (1)
  electronics: count=4, earliest=2023-10-29, latest=2023-11-11, top_day=2023-10-29 (1)
    soldering (2)
    debugging (2)
  documenting: count=3, earliest=2023-10-26, latest=2023-11-14, top_day=2023-10-26 (1)
    productdesign (1)
    entrepreneurship (1)
  orgmode: count=2, earliest=2023-10-25, latest=2023-11-10, top_day=2023-10-25 (1)
    emacslisp (1)
  terraform: count=2, earliest=2023-10-26, latest=2023-11-13, top_day=2023-10-26 (1)
    aws (1)
    github (1)
  soldering: count=2, earliest=2023-10-29, latest=2023-10-30, top_day=2023-10-29 (1)
    electronics (2)
  entrepreneurship: count=2, earliest=2023-11-02, latest=2023-11-14, top_day=2023-11-02 (1)
    python (1)
    documenting (1)

```

With task filtering:
```bash
orgstats --filter simple -n 5 examples/ARCHIVE_small
```

```
Processing examples/ARCHIVE_small...

Total tasks:  14

Done tasks:  14

Top tags:
  projectmanagement: count=6, earliest=2023-10-19, latest=2023-11-09, top_day=2023-10-25 (2)
    jira (3)
  debugging: count=4, earliest=2023-10-20, latest=2023-11-11, top_day=2023-10-20 (1)
    erlang (1)
    xmpp (1)
    arduino (1)
  jira: count=3, earliest=2023-10-25, latest=2023-11-09, top_day=2023-10-25 (1)
    projectmanagement (3)
  electronics: count=2, earliest=2023-10-29, latest=2023-11-11, top_day=2023-10-29 (1)
    soldering (1)
    debugging (1)
  customersupport: count=2, earliest=2023-11-08, latest=2023-11-08, top_day=2023-11-08 (2)
    debugging (1)
```

### Available Options

- `--max-results N`, `-n N` - Maximum number of results to display (default: 10)
- `--max-relations N` - Maximum number of relations to display for each tag (default: 3)
- `--filter TYPE`, `-f TYPE` - Filter tasks by difficulty: `simple`, `regular`, `hard`, or `all` (default: `all`)
- `--mapping FILE` - Tag name mapping JSON file to use.
- `--show CATEGORY` - what category of data to process: `tags`, `heading` or `body` (default: `tags`)
- `--exclude FILE` - File with tags to exclude (one per line, replaces default)

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
