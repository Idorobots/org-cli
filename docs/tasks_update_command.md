# `org tasks update`

Update one matched task heading in an Org document.

## Usage

```bash
poetry run org tasks update [OPTIONS] [FILE ...]
```

## Selector switches

- `--query-title TEXT` - Match task by heading title text.
- `--query-id TEXT` - Match task by heading `ID` property.

Provide exactly one selector: `--query-title` or `--query-id`.

## Update switches

- `--level N` - New heading level.
- `--todo KEY` - New TODO state (empty string clears).
- `--priority P` - New priority marker (empty string clears).
- `--comment BOOL` - Set `COMMENT` flag (`true` or `false` only).
- `--title TEXT` - New heading title text (empty string clears).
- `--id TEXT` - New `ID` property value (empty string clears).
- `--counter COUNTER` - New completion counter (empty string clears).
- `--deadline TIMESTAMP` - New deadline timestamp (empty string clears).
- `--scheduled TIMESTAMP` - New scheduled timestamp (empty string clears).
- `--closed TIMESTAMP` - New closed timestamp (empty string clears).
- `--category TEXT` - New `CATEGORY` property value (empty string clears).
- `--body TEXT` - New task body text.
- `--parent ID_OR_TITLE` - Move task under a new parent heading; empty string moves task to top level.
- `--tags TAG1,TAG2` - Set comma-separated tags (empty string clears all tags).
- `--properties JSON` - Set properties from a JSON object (empty string clears all properties).
- `--add-clock-entry TEXT` - Add one clock entry line (repeatable).
- `--remove-clock-entry TEXT` - Remove one existing clock entry line (repeatable).
- `--add-repeat TEXT` - Add one repeat line (repeatable).
- `--remove-repeat TEXT` - Remove one existing repeat line (repeatable).
- `--add-tag TAG` - Add one tag if missing (repeatable).
- `--remove-tag TAG` - Remove one existing tag (repeatable).
- `--add-property P=V` - Add or replace one property (repeatable).
- `--remove-property P` - Remove one existing property key (repeatable).

## Matching and validation rules

- Input files are resolved from `[FILE ...]`.
- Matching checks all resolved files.
- Selector must match exactly one task across all files.
- No matches or multiple matches return an error.
- Parent lookup checks heading `ID` first, then heading title.
- Parent lookup errors on missing parent or ambiguous title matches.
- Parent cannot be the updated task itself or one of its descendants.
- `--level` must be greater than parent level for child headings.
- Top-level headings can use any positive level.
- If `--parent` is provided without `--level`, level is adjusted automatically (`parent + 1`, or `1` for top-level).
- `--tags` cannot be combined with `--add-tag` or `--remove-tag`.
- `--properties` cannot be combined with `--add-property` or `--remove-property`.
- Any `--remove-*` switch errors when the target entry is not present on the task.

## Examples

1) Update title of a task

```bash
poetry run org tasks update --query-id 23 --title "Foo"
```

2) Update TODO state and set closed timestamp

```bash
poetry run org tasks update --query-title "Foo" --todo DONE --closed "<2026-04-13>"
```

3) Move task under a new parent and set explicit valid level

```bash
poetry run org tasks update --query-id 23 --parent project-1 --level 3
```

4) Clear tags and properties

```bash
poetry run org tasks update --query-id 23 --tags "" --properties ""
```

5) Add and remove specific tags and properties

```bash
poetry run org tasks update --query-id 23 --add-tag urgent --remove-tag waiting --add-property ETA=2026-04-20 --remove-property LAST_REPEAT
```

6) Add and remove specific logbook entries

```bash
poetry run org tasks update --query-id 23 --add-clock-entry "CLOCK: [2026-04-14 Tue 09:00]--[2026-04-14 Tue 10:00] =>  1:00" --add-repeat "- State \"DONE\" from \"TODO\" [2026-04-14 Tue 10:00]"
```
