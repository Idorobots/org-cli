# AGENTS.md - Developer Guide for Coding Agents

This document provides essential information for AI coding agents working in the `orgstats` repository.

## Project Overview

**orgstats** is a Python CLI tool that analyzes Emacs Org-mode archive files to extract task statistics and generate frequency analysis of tags, headline words, and body words.

**Tech Stack:**
- Python 3.14.2
- `orgparse` library (0.4.20251020)
- `pytest` for testing (97% code coverage)

**Project Structure:**
```
orgstats/
├── src/
│   ├── core.py          # Core business logic (100% coverage)
│   ├── cli.py           # CLI interface
│   └── main.py          # Entry point (backwards compatible)
├── tests/
│   ├── fixtures/        # Test Org-mode files
│   ├── test_*.py        # 78 tests across 7 test files
│   └── __init__.py
├── examples/            # Sample Org-mode archive files
├── requirements.txt     # Python dependencies (includes pytest)
├── dev/                 # Python virtual environment (git-ignored)
└── .gitignore
```

## Development Setup

### Initial Setup
```bash
# Create virtual environment
python -m venv dev

# Activate virtual environment
source dev/bin/activate  # Linux/Mac
# OR
.\dev\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Basic usage
python src/main.py examples/ARCHIVE_small

# View help and all options
python src/main.py --help

# Limit number of results displayed
python src/main.py --max-results 50 examples/ARCHIVE_small
python src/main.py -n 50 examples/ARCHIVE_small

# Use custom stopword files (one word per line)
python src/main.py --exclude-tags my_tags.txt examples/ARCHIVE_small
python src/main.py --exclude-heading my_heading_words.txt examples/ARCHIVE_small
python src/main.py --exclude-body my_body_words.txt examples/ARCHIVE_small

# Combine multiple options
python src/main.py -n 25 --exclude-tags tags.txt --exclude-heading heading.txt examples/ARCHIVE_small

# Process multiple files
python src/main.py file1.org file2.org file3.org

# Or make it executable
chmod +x src/main.py
./src/main.py examples/ARCHIVE_small
```

**CLI Arguments:**
- `files` - Org-mode archive files to analyze (positional arguments)
- `--max-results N` / `-n N` - Maximum number of results to display (default: 100)
- `--exclude-tags FILE` - File with tags to exclude (one per line, replaces default TAGS)
- `--exclude-heading FILE` - File with heading words to exclude (one per line, replaces default HEADING)
- `--exclude-body FILE` - File with body words to exclude (one per line, replaces default BODY)
- `--help` / `-h` - Show help message

## Build/Lint/Test Commands

### Testing
**Status:** 93 tests with 97% code coverage ✓

```bash
# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# Run a single test file
pytest tests/test_normalize.py

# Run a specific test function
pytest tests/test_normalize.py::test_normalize_basic

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Run with HTML coverage report
pytest --cov=src --cov-report=html

# Run tests in parallel (faster)
pytest -n auto
```

**Test Categories:**
- `test_mapped.py` - Tag mapping logic (9 tests)
- `test_normalize.py` - Tag normalization (13 tests)
- `test_clean.py` - Stop word filtering (13 tests)
- `test_analyze.py` - Core analysis function (18 tests)
- `test_integration.py` - End-to-end tests (13 tests)
- `test_cli.py` - CLI subprocess tests (8 tests)
- `test_cli_direct.py` - CLI direct tests (4 tests)
- `test_cli_argparse.py` - Argparse functionality tests (15 tests)

### Linting & Formatting
**Status:** ✅ Fully configured with Ruff and mypy

**Tools Configured:**
- **Ruff** - Fast, comprehensive linter and formatter (replaces Flake8, Black, isort, pyupgrade)
- **mypy** - Static type checker with strict mode enabled
- **Pre-commit hook** - Automatically runs all checks before commits

**Configuration:**
- All settings in `pyproject.toml`
- Line length: 100 characters
- Target Python: 3.14
- Strict type checking enabled
- Import sorting configured

**Commands:**
```bash
# Run all linting checks
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/

# Type checking
mypy src/

# Run all checks (what pre-commit hook runs)
ruff format --check src/ tests/ && ruff check src/ tests/ && mypy src/ && pytest
```

**Pre-commit Hook:**
The repository has a git pre-commit hook installed at `.git/hooks/pre-commit` that automatically:
1. Checks code formatting
2. Runs linter checks
3. Runs type checking
4. Runs test suite

If any check fails, the commit is blocked. The hook activates automatically on `git commit`.

### Dependency Management
```bash
# Install new dependency
pip install <package>
pip freeze > requirements.txt

# Or manually add to requirements.txt with pinned version
```

## Code Style Guidelines

### General Principles
- Keep code simple, readable, and functional
- Prefer functional programming patterns (comprehensions, pure functions)
- Minimize dependencies - only add when truly necessary
- Self-documenting code over excessive comments

### Python Style

**PEP 8 Compliance:**
- Use **4 spaces** for indentation (not 2, not tabs)
- Maximum line length: 100 characters
- Two blank lines between top-level functions/classes
- One blank line between methods

**Indentation:**
```python
# CORRECT (4 spaces)
def mapped(mapping, t):
    if t in mapping:
        return mapping[t]
    else:
        return t

# Note: All code now follows PEP 8 with 4-space indentation
```

### Imports
```python
# Standard library imports first
import sys
import os

# Third-party imports next
import orgparse

# Local imports last (when applicable)
from src.utils import helper
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
git add src/main.py
git commit -m "Add feature: description"

# Push to remote (when configured)
git push origin feature/description
```

## Common Tasks

### Adding a New Tag Mapping
Edit the `MAP` dictionary in `src/core.py`:
```python
MAP = {
    'test': "testing",
    'newabbrev': "canonical_term",  # Add here
}
```

### Adding Stop Words
Edit `TAGS`, `HEADING`, or `WORDS` sets in `src/core.py`:
```python
TAGS = {
    "comp", "computer", "newtag",  # Add here
}
```

### Performance Optimization
- Use set operations for membership tests
- Prefer comprehensions over explicit loops
- Consider generators for large file processing

---

**Last Updated:** 2026-02-06  
**Maintained By:** AI Coding Agents
