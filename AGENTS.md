# AGENTS.md - Developer Guide for Coding Agents

This document provides essential information for AI coding agents working in the `orgstats` repository.

## Project Overview

**orgstats** is a Python CLI tool that analyzes Emacs Org-mode archive files to extract task statistics and generate frequency analysis of tags, headline words, and body words.

**Tech Stack:**
- Python 3.14.2
- Poetry for build & dependency management
- See `pyproject.toml` for the dependencies & their versions.

**Project Structure:**
```
orgstats/
├── src/
│   └── orgstats/             # Main package
│       ├── __init__.py       # Package initialization (exports main, version, etc.)
│       ├── __main__.py       # Entry point for `python -m orgstats`
│       ├── cli.py            # CLI interface
│       └── core.py           # Core business logic
├── tests/
│   ├── fixtures/             # Test Org-mode files
│   ├── test_*.py             # Logic test files
│   ├── conftest.py           # Shared test fixtures
│   └── __init__.py
├── examples/                 # Sample Org-mode archive files
├── pyproject.toml            # Poetry configuration & build settings
├── poetry.lock               # Poetry dependency lock file
└── .gitignore
```

## Development Setup
Several helpful Poetry tasks are defined in `pyproject.toml`  that automate running mundane tasks. These tasks should be used whenever possible instead of running individual commands.

### Initial Setup
```bash
# Install all dependencies and the package itself
poetry install
```

### Running the Application
```bash
# Recommended: Use the installed CLI command (after poetry install)
poetry run orgstats examples/ARCHIVE_small

# View help and all options
poetry run orgstats --help

# Limit number of results displayed
poetry run orgstats --max-results 50 examples/ARCHIVE_small
poetry run orgstats -n 50 examples/ARCHIVE_small

# Limit number of tags displayed in Top tags section
poetry run orgstats --max-tags 3 examples/ARCHIVE_small
poetry run orgstats --max-tags 0 examples/ARCHIVE_small  # Omit Top tags section entirely

# Limit number of tag groups displayed
poetry run orgstats --max-groups 3 examples/ARCHIVE_small
poetry run orgstats --max-groups 0 examples/ARCHIVE_small  # Omit Tag groups section entirely

# Filter by task difficulty (requires --with-gamify-category)
poetry run orgstats --with-gamify-category --filter-category hard examples/ARCHIVE_small
poetry run orgstats --with-gamify-category --filter-category simple -n 20 examples/ARCHIVE_small

# Use first tag as category
poetry run orgstats --with-tags-as-category examples/ARCHIVE_small

# Combine both preprocessors (tags will override gamify)
poetry run orgstats --with-gamify-category --with-tags-as-category examples/ARCHIVE_small

# Filter by tag-based category
poetry run orgstats --with-tags-as-category --filter-category work examples/ARCHIVE_small

# Show different data categories
poetry run orgstats --use tags examples/ARCHIVE_small       # Analyze tags (default)
poetry run orgstats --use heading examples/ARCHIVE_small    # Analyze headline words
poetry run orgstats --use body examples/ARCHIVE_small       # Analyze body words

# Use custom stopword file (one word per line)
poetry run orgstats --exclude my_words.txt examples/ARCHIVE_small

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

# Filter by regex patterns
poetry run orgstats --filter-tag "^test" examples/ARCHIVE_small         # Tags starting with "test"
poetry run orgstats --filter-heading "bug|fix" examples/ARCHIVE_small   # Headings containing "bug" or "fix"
poetry run orgstats --filter-body "TODO:" examples/ARCHIVE_small        # Body containing "TODO:"

# Combine multiple options
poetry run orgstats -n 25 --with-gamify-category --filter-category regular --exclude words.txt examples/ARCHIVE_small

# Process multiple files
poetry run orgstats file1.org file2.org file3.org
```

**CLI Arguments:**
- `files` - Org-mode archive files to analyze (positional arguments)
- `--max-results N` / `-n N` - Maximum number of results to display (default: 10)
- `--max-tags N` - Maximum number of tags to display in Top tags section (default: 5, use 0 to omit section)
- `--max-relations N` - Maximum number of relations to display per item (default: 5, use 0 to omit sections)
- `--max-groups N` - Maximum number of tag groups to display (default: 5, use 0 to omit section)
- `--min-group-size N` - Minimum group size to display (default: 2)
- `--buckets N` - Number of time buckets for timeline charts (default: 50, minimum: 20)
- `--with-gamify-category` - Preprocess nodes to set category property based on gamify_exp value (disabled by default)
- `--with-tags-as-category` - Preprocess nodes to set category property based on first tag (disabled by default)
- `--category-property PROPERTY` - Property name for category histogram and filtering (default: CATEGORY)
- `--filter-category VALUE` - Filter tasks by category property value (e.g., simple, regular, hard, none, or custom). Use 'all' to skip category filtering (default: all)
  - When `--with-gamify-category` is enabled: categories are simple, regular, hard based on gamify_exp
  - When `--with-tags-as-category` is enabled: category is the first tag on the task
  - Without preprocessing: uses existing property values in org files (or "none" if missing)
  - Can filter by any custom category value
- `--use CATEGORY` - Category to display: tags, heading, or body (default: tags)
- `--exclude FILE` - File with words to exclude (one per line, replaces default exclusion list)
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
- `--help` / `-h` - Show help message

Date formats: `YYYY-MM-DD`, `YYYY-MM-DDThh:mm`, `YYYY-MM-DDThh:mm:ss`, `YYYY-MM-DD hh:mm`, `YYYY-MM-DD hh:mm:ss`

## Build/Lint/Test Commands
- All checks should be run with a single command:
```bash
# Run all validation checks
poetry run task check
```

- If any errors appear it is worth trying to fix them automatically with the other commands:
```bash
# Attempt to fix formatting errors automatically
poetry run task format

# Attempt to fix linting errors automatically
poetry run task lint-fix
```

- It is sufficient to run the validation command, there is no need to separately check that the application works.
- The validation command will also run the newly introduced tests, no need to run them separately.
- Validation should be run after applying multiple changes to avoid repeated checks.

### Linting & Formatting
**Tools Configured:**
- **Ruff** - Fast, comprehensive linter and formatter
- **mypy** - Static type checker with strict mode enabled
- **Pre-commit hook** - Automatically runs all checks before commits

**Configuration:**
- All settings in `pyproject.toml`
- Line length: 100 characters
- Target Python: 3.14
- Strict type checking enabled
- Import sorting configured

**Pre-commit Hook:**
The repository has a git pre-commit hook installed at `.git/hooks/pre-commit` that automatically:
1. Checks code formatting
2. Runs linter checks
3. Runs type checking
4. Runs test suite

If any check fails, the commit is blocked. The hook activates automatically on `git commit`.

### Testing

**Test Categories:**
- `test_mapped.py` - Tag mapping logic
- `test_normalize.py` - Tag normalization
- `test_clean.py` - Stop word filtering
- `test_analyze.py` - Core analysis function
- `test_integration.py` - End-to-end tests
- `test_cli.py` - CLI subprocess tests
- `test_cli_direct.py` - CLI direct tests
- `test_cli_argparse.py` - Argparse functionality tests

### Dependency Management
```bash
# Install new dependency
poetry add <package>
```

## Code Style Guidelines

### General Principles
- Keep code simple, readable, and functional
- Prefer functional programming patterns (comprehensions, pure functions)
- Minimize dependencies - only add when truly necessary
- Self-documenting code over excessive comments
- Avoid using the `Any` type as much as possible. Avoid changing any existing types to `Any`.
- Avoid adding comments explaining which method of a class is used (things like `# Uses Frequency.__eq__(int)`).
- Avoid adding comments unless the behavior is not obivous.
- Avoid adding updates to comments (`now with extra functionality`), prefer to skip the addition or rewrite the comment if the change is significant.
- Avoid mocking in tests as much as possible.
- Avoid using default function arguments values.
- Target test coverage is 90% or above.
- Backwards compatibility is not required, no need to ensure it.

### Linting Policy
- Under no circumstances should linter rules be disabled using `noqa` comments
- If code triggers a linter error, refactor the code to fix the underlying issue instead
- Common refactoring strategies:
  - Extract functions to reduce complexity (PLR0912: too many branches, PLR0915: too many statements)
  - Split long functions into smaller, focused functions (C901: too complex)
  - Use guard clauses to reduce nesting (PLR1702: too many nested blocks)
- The only acceptable exceptions are rules already ignored in `pyproject.toml` for specific scenarios

### Python Style

**PEP 8 Compliance:**
- Use **4 spaces** for indentation (not 2, not tabs)
- Maximum line length: 100 characters
- Two blank lines between top-level functions/classes
- One blank line between methods

### Imports
```python
# Standard library imports first
import sys
import os

# Third-party imports next
import orgparse

# Local package imports last
from orgstats.core import analyze, Frequency
from orgstats.cli import main
```

### Naming Conventions
- **Functions/variables:** `snake_case` (e.g., `normalize`, `total_count`, `analyze_nodes`)
- **Constants:** `UPPER_CASE` (e.g., `MAP`, `TAGS`, `HEADING`, `WORDS`)
- **Classes:** `PascalCase` (e.g., `NodeAnalyzer`, `TagMapper`)
- **Private functions:** `_leading_underscore` (e.g., `_internal_helper`)

### String Quotes
- **Prefer double quotes** for strings: `"hello"` not `'hello'`
- Use single quotes for strings containing double quotes: `'He said "hello"'`
- Use triple double-quotes for docstrings: `"""This is a docstring."""`

### Type Hints
**Recommended** for new code:
```python
def normalize(tags: set[str]) -> set[str]:
    """Normalize and map tags to canonical forms."""
    norm = {t.lower().strip().replace(".", "") for t in tags}
    return {mapped(MAP, t) for t in norm}

def analyze(nodes: list) -> tuple[int, int, dict, dict, dict]:
    """Analyze org-mode nodes and return statistics."""
    # Implementation
    pass
```

### Data Structures
- **Prefer comprehensions** over loops when building collections:
  ```python
  # GOOD
  tags = {t.lower().strip() for t in node.tags}

  # AVOID
  tags = set()
  for t in node.tags:
      tags.add(t.lower().strip())
  ```

- **Use descriptive dictionary keys:**
  ```python
  # Return named tuples or dictionaries with clear keys
  return (total, done, tags, heading, words)  # Current style
  # OR for clarity:
  return {
      "total": total,
      "done": done,
      "tags": tags,
      "heading": heading,
      "words": words
  }
  ```

### Error Handling
```python
# Always handle file operations gracefully
try:
    with open(name) as f:
        contents = f.read()
except FileNotFoundError:
    print(f"Error: File '{name}' not found")
    sys.exit(1)
except PermissionError:
    print(f"Error: Permission denied for '{name}'")
    sys.exit(1)

# Check for None returns
ns = orgparse.loads(contents)
if ns is not None:  # Use "is not None" instead of "!= None"
    nodes = nodes + list(ns[1:])
```

### Comments
- Use comments sparingly - prefer self-documenting code
- **NOTE comments** for workarounds or non-obvious behavior:
  ```python
  # NOTE: Making the file parseable - orgparse doesn't handle 24:00 time format
  contents = f.read().replace("24:00", "00:00")
  ```
- Add docstrings for all functions:
  ```python
  def clean(allowed: set, tags: dict) -> dict:
      """Remove tags from the allowed set.

      Args:
          allowed: Set of tags to filter out
          tags: Dictionary of tag frequencies

      Returns:
          Dictionary with allowed tags removed
      """
      return {t: tags[t] for t in tags if t not in allowed}
  ```

## Domain-Specific Knowledge

### Org-mode Format
- Org-mode is a plain-text markup format from Emacs
- Tasks have TODO/DONE states
- Tasks can have tags (e.g., `:testing:devops:`)
- Tasks can have repeated/scheduled entries
- Time format quirk: `24:00` must be normalized to `00:00`

### Tag Normalization
- Tags are lowercased and stripped
- Punctuation is removed: `.,:;!?`
- Tags are mapped using `MAP` dictionary for consolidation
- Common/noise tags filtered via `TAGS`, `HEADING`, `WORDS` sets

## Git Workflow

```bash
# Check status
git status

# Create feature branch
git checkout -b feature/description

# Stage and commit
git add src/cli.py
git commit -m "Add feature: description"

# Push to remote (when configured)
git push origin feature/description
```

## Common Tasks

### Running validation checks
```bash
# Run all validation checks
poetry run task check
```

### Performance Optimization
- Use set operations for membership tests
- Prefer comprehensions over explicit loops
- Consider generators for large file processing

## Other rules
- Be concise and straight-to-the-point.
- Avoid emojis and colorful language.
- Do not summarize work done unless explicitly asked to do that.
- When a file requires multiple changes, apply them all to the file in a single tool call instead of performing each edit separately.

---

**Last Updated:** 2026-02-08
**Maintained By:** AI Coding Agents (sometimes)
