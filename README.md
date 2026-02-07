# orgstats

Analyze Emacs Org-mode archive files to extract task statistics and tag/word frequencies.

## Installation

```bash
python -m venv dev
source dev/bin/activate
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
python src/cli.py <org-file> [<org-file> ...]
```

### Options

```bash
# Display help
python src/cli.py --help

# Limit number of results
python src/cli.py -n 10 examples/ARCHIVE_small

# Filter by task difficulty (sorts and displays by selected type)
python src/cli.py --tasks simple examples/ARCHIVE_small   # Simple tasks (gamify_exp < 10)
python src/cli.py --tasks regular examples/ARCHIVE_small  # Regular tasks (10 ≤ exp < 20)
python src/cli.py --tasks hard examples/ARCHIVE_small     # Hard tasks (exp ≥ 20)
python src/cli.py --tasks total examples/ARCHIVE_small    # All tasks (default)

# Use custom stopword files
python src/cli.py --exclude-tags tags.txt examples/ARCHIVE_small
python src/cli.py --exclude-heading heading.txt examples/ARCHIVE_small
python src/cli.py --exclude-body body.txt examples/ARCHIVE_small

# Combine options
python src/cli.py --tasks hard -n 10 --exclude-tags tags.txt examples/ARCHIVE_small
```

### Example Output

```bash
python src/cli.py --tasks total examples/ARCHIVE_small
```

```
Processing examples/ARCHIVE_small...

Total tasks:  33
Done tasks:  33

Top tags:
 [('projectmanagement', 10), ('debugging', 8), ('jira', 6), ...]

Top words in headline:
 [('ejabberd', 8), ('prepare', 4), ('session', 3), ...]

Top words in body:
 [...]
```

With task filtering:
```bash
python src/cli.py --tasks hard -n 5 examples/ARCHIVE_small
```

```
Top tags:
 [('hardtag', 5), ('mediumtag', 2), ...]
```

### Available Options

- `--max-results N`, `-n N` - Maximum number of results to display (default: 100)
- `--tasks TYPE` - Task type to display and sort by: `simple`, `regular`, `hard`, or `total` (default: `total`)
- `--exclude-tags FILE` - File with tags to exclude (one per line, replaces default)
- `--exclude-heading FILE` - File with heading words to exclude (one per line, replaces default)
- `--exclude-body FILE` - File with body words to exclude (one per line, replaces default)

### Task Difficulty Levels

Tasks are classified based on their `gamify_exp` property:
- **Simple**: `gamify_exp < 10`
- **Regular**: `10 ≤ gamify_exp < 20`
- **Hard**: `gamify_exp ≥ 20`

Tasks without `gamify_exp` or with invalid values default to regular difficulty.

## Testing

```bash
pytest                                     # Run all tests
pytest tests/test_normalize.py             # Run single file
pytest --cov=src --cov-report=term-missing # With coverage
```

## Project Structure

- `src/core.py` - Core analysis logic
- `src/cli.py` - CLI interface and entry point
- `tests/` - Test suite (150 tests, 95% coverage)
