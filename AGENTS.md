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
├── dev/                      # Python virtual environment (git-ignored)
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

# Alternative: Run as a Python module
poetry run python -m orgstats examples/ARCHIVE_small

# Fallback: Direct module execution
poetry run python src/orgstats/cli.py examples/ARCHIVE_small

# View help and all options
poetry run orgstats --help

# Limit number of results displayed
poetry run orgstats --max-results 50 examples/ARCHIVE_small
poetry run orgstats -n 50 examples/ARCHIVE_small

# Filter by task difficulty
poetry run orgstats --tasks hard examples/ARCHIVE_small
poetry run orgstats --tasks simple -n 20 examples/ARCHIVE_small

# Use custom stopword files (one word per line)
poetry run orgstats --exclude-tags my_tags.txt examples/ARCHIVE_small
poetry run orgstats --exclude-heading my_heading_words.txt examples/ARCHIVE_small
poetry run orgstats --exclude-body my_body_words.txt examples/ARCHIVE_small

# Combine multiple options
poetry run orgstats -n 25 --tasks regular --exclude-tags tags.txt --exclude-heading heading.txt examples/ARCHIVE_small

# Process multiple files
poetry run orgstats file1.org file2.org file3.org
```

**CLI Arguments:**
- `files` - Org-mode archive files to analyze (positional arguments)
- `--max-results N` / `-n N` - Maximum number of results to display (default: 100)
- `--tasks TYPE` - Task type to display and sort by: simple, regular, hard, or total (default: total)
  - `simple` - Tasks with gamify_exp < 10
  - `regular` - Tasks with 10 ≤ gamify_exp < 20
  - `hard` - Tasks with gamify_exp ≥ 20
  - `total` - All tasks combined (default)
- `--exclude-tags FILE` - File with tags to exclude (one per line, replaces default TAGS)
- `--exclude-heading FILE` - File with heading words to exclude (one per line, replaces default HEADING)
- `--exclude-body FILE` - File with body words to exclude (one per line, replaces default BODY)
- `--help` / `-h` - Show help message

## Build/Lint/Test Commands
All checks should be run with a single command:

```bash
# Run all validation checks
poetry run task check

# Attempt to fix formatting errors automatically
poetry run task format

# Attempt to fix linting errors automatically
poetry run task lint-fix
```
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

---

**Last Updated:** 2026-02-08
**Maintained By:** AI Coding Agents (sometimes)
