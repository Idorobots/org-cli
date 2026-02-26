# `org query`

Run jq-style queries over loaded Org files.

For the query language itself, see `query_language.md`.

## Usage

```bash
poetry run org query [OPTIONS] QUERY [FILE ...]
```

## Command-specific switches

- `--max-results`, `-n` - Limit emitted values.
- `--offset` - Skip first N emitted values.
- `--todo-keys`, `--done-keys` - Define completion key sets visible to query variables.
- `--color/--no-color` - Force color mode.

When you use `--offset` or `--max-results`, include `$offset` and `$limit` in the query expression.

## Examples

1) Fetch headings from all tasks

```bash
poetry run org query '.[][] | .heading' examples/ARCHIVE_small
```

2) Fetch headings of completed tasks

```bash
poetry run org query '.[][] | select(.todo in $done_keys) | .heading' \
  examples/ARCHIVE_small
```

Example output (ellided):

```text
Prepare stories for the refinement.
Prepare a document for team onboarding to Ejabberd.
...
```

3) Fetch a paged window of headings

```bash
poetry run org query '[ .[][] | .heading ][ $offset : $offset + $limit ]' \
  --offset 5 \
  --max-results 5 \
  examples/ARCHIVE_small
```

4) Fetch headings for tasks tagged `Debugging`, then page results

```bash
poetry run org query '[ .[][] | select("Debugging" in .tags) | .heading ][ $offset : $offset + $limit ]' \
  --offset 2 \
  --max-results 8 \
  examples/ARCHIVE_small
```

5) Fetch tasks that are not completed yet

```bash
poetry run org query '[ .[][] | select(not(.todo in $done_keys)) ][ $offset : $offset + $limit ]' \
  --offset 0 \
  --max-results 5 \
  examples/ARCHIVE_small
```

Example output (ellided):

```org
# examples/ARCHIVE_small
* CANCELLED Refine some more tasks with the team.                                     :ProjectManagement
SCHEDULED: <2023-10-19 czw>
:PROPERTIES:
...
:END:
...
```

## Output

- Plain values are printed line-by-line.
- Org node/date values are rendered as Org-formatted blocks.
- Empty result stream prints `No results`.
