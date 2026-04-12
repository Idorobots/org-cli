# `org tasks create`

Create and insert a new task heading into an Org document.

## Usage

```bash
poetry run org tasks create [OPTIONS] [FILE ...]
```

## Command-specific switches

- `--level N` - Heading level. Defaults to `1`, or `parent_level + 1` when `--parent` is set.
- `--todo KEY` - Todo state for the new heading.
- `--priority P` - Heading priority marker.
- `--is-comment` - Mark heading as `COMMENT`.
- `--title TEXT` - Heading title text.
- `--counter COUNTER` - Completion counter content.
- `--tag TAG` - Attach tag (repeatable).
- `--heading HEADING` - Full heading line. Mutually exclusive with `--level`, `--todo`, `--priority`, `--is-comment`, `--title`, `--counter`, and `--tag`.
- `--deadline TIMESTAMP` - Add deadline timestamp.
- `--scheduled TIMESTAMP` - Add scheduled timestamp.
- `--closed TIMESTAMP` - Add closed timestamp.
- `--property KEY=VALUE` - Add heading property (repeatable).
- `--category TEXT` - Set `CATEGORY` property.
- `--id TEXT` - Set `ID` property.
- `--body TEXT` - Task body text.
- `--parent ID_OR_TITLE` - Insert as child of the matching heading.
- `--file FILE` - Target file to update. Overrides default file resolution from `[FILE ...]`.

## Parent matching

- Parent lookup checks heading `ID` first, then heading title.
- If no heading matches, command exits with an error.
- If multiple headings match, command exits with an error.

## Validation

- Generated heading content is validated with `Heading.from_source` before file updates.
- Invalid heading source (for example malformed timestamps) returns a CLI error and does not modify files.

## Examples

1) Create a top-level task in the default file

```bash
poetry run org tasks create \
  --todo TODO \
  --title "Update the docs" \
  --tag Docs \
  --body "Update the documentation..."
```

2) Create a top-level task in a specific file from inputs

```bash
poetry run org tasks create \
  --title "Do some stuff" \
  --file path/to/file.org
```

3) Create a child task under a parent heading

```bash
poetry run org tasks create \
  --title "Do some stuff" \
  --parent "Update the docs"
```
