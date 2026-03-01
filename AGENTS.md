# AGENTS.md - Developer Guide for Coding Agents

This document provides essential information for AI coding agents working in the `org-cli` repository.

## Project Overview

**org-cli** is a Python CLI for Org-mode archives. It supports query-style data extraction, task listing, and statistical analysis.

Top-level commands:

- `org query`
- `org stats summary`
- `org stats tasks`
- `org stats tags`
- `org stats groups`
- `org tasks list`

**Project Toolchain:**

- Python `>=3.12,<4.0` (configured in `pyproject.toml`)
- Poetry for dependency management and packaging
- Runtime dependencies: `orgparse`, `typer`, `rich`, `parsy`
- Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`, `pyright`, `taskipy`

**Project Structure:**

```
org-cli/
├── src/
│   └── org/
│       ├── cli.py
│       ├── config.py
│       ├── cli_common.py
│       ├── analyze.py
│       ├── filters.py
│       ├── tui.py
│       ├── query_language/
│       └── commands/
│           ├── query.py
│           ├── stats/
│           │   ├── summary.py
│           │   ├── tasks.py
│           │   ├── tags.py
│           │   └── groups.py
│           └── tasks/
│               └── list.py
├── tests/
├── examples/
├── docs/
├── pyproject.toml
└── poetry.lock
```

## Documentation

- Entry point: `docs/index.md`
- Query language reference: `docs/query_language.md`

## Development Setup
Several helpful Poetry tasks are defined in `pyproject.toml`  that automate running mundane tasks. These tasks should be used whenever possible instead of running individual commands.

### Initial Setup
```bash
# Install all dependencies and the package itself
poetry install
```

### Running the Application
```bash
# View command tree
poetry run org --help

# Query command
poetry run org query '.[][] | .heading' -n 5 examples/ARCHIVE_small

# Summary stats
poetry run org stats summary --max-tags 3 --max-groups 2 examples/ARCHIVE_small

# Task-only stats with derived categories from gamify_exp
poetry run org stats tasks --with-gamify-category examples/ARCHIVE_small

# Focused tag stats
poetry run org stats tags --show Debugging,Jira --max-relations 3 examples/ARCHIVE_small

# Explicit groups
poetry run org stats groups --group Debugging,Erlang --group ProjectManagement,Jira examples/ARCHIVE_small

# Task listing with filters and ordering
poetry run org tasks list --filter-not-completed --order-by-level --order-by-timestamp-asc examples/ARCHIVE_small
```

Command options evolve; use the generated help for exact flags:

```bash
poetry run org --help
poetry run org query --help
poetry run org stats --help
poetry run org stats summary --help
poetry run org stats tasks --help
poetry run org stats tags --help
poetry run org stats groups --help
poetry run org tasks --help
poetry run org tasks list --help
```

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
from org.analyze import analyze, Frequency
from org.cli import main
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
git add src/org/cli.py
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

**Last Updated:** 2026-02-26
**Maintained By:** AI Coding Agents (sometimes)
