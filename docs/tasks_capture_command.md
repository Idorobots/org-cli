# `org tasks capture`

Create and insert one task heading from a named capture template.

## Usage

```bash
poetry run org tasks capture [OPTIONS] [TEMPLATE_NAME]
```

- If `TEMPLATE_NAME` is omitted, the command shows a numbered template picker.
- Picker input is numeric only.

## Command-specific switches

- `--file FILE` - Override template `file` target path.
- `--parent SELECTOR` - Override template `parent` selector expression.
- `--set KEY=VALUE` - Set a template placeholder value without prompting. Repeatable.

When provided, CLI switch values take precedence over template config values.

## Configuration

Capture templates live under `capture.templates` in `.org-cli.yaml`.

Template fields:

- `file` (required): target Org file path.
- `content` (required): Org heading template text.
- `parent` (optional): selector expression wrapped automatically as `.[] | select(<selector>)` and required to resolve to exactly one heading.

Example:

```yaml
capture:
  templates:
    quick:
      file: tasks.org
      content: "* TODO {{title}}"
    project-task:
      file: tasks.org
      parent: '.id == "project-1"'
      content: |
        ** TODO {{title}}
        :PROPERTIES:
        :ID: {{uuid}}
        :CREATED: {{now}}
        :END:
```

## Placeholders

- Static placeholders (no prompt): `{{uuid}}`, `{{today}}`, `{{now}}`, `{{id}}`.
- `{{today}}` renders as an active Org timestamp date: `<YYYY-MM-DD Day>`.
- `{{now}}` renders as an active Org timestamp date/time: `<YYYY-MM-DD Day HH:MM>`.
- `{{id}}` renders as the next numeric task id for the target file (`len(all headings) + 1`).
- Document metadata placeholders are explicitly supported: `{{document_category}}`, `{{document_filename}}`, `{{document_title}}`, `{{document_author}}`, `{{document_description}}`.
- When capture resolves a parent heading (via template `parent` or CLI `--parent`), parent placeholders are available: `{{parent_category}}`, `{{parent_title}}`, `{{parent_todo}}`, `{{parent_id}}`.
- Any other placeholder prompts once and reuses the entered value for repeats.
- In interactive terminals, capture runs as a full-screen live editor: the template is the main body and the footer is pinned to the two bottom-most terminal lines.
- The footer is split into two lines: top line shows a left-aligned progress marker (`Value 2/5`) and right-aligned key bindings; second line shows the current value prompt.
- The footer is separated from the template body by a horizontal rule.
- Long value prompts wrap onto additional lines as needed, and the footer grows beyond two lines to keep the full input visible.
- The prompt accepts pasted input from bracketed paste (for example middle-click paste in supporting terminals) and Ctrl+P style paste mappings.
- The currently prompted placeholder value is emphasized with a brighter background color in the preview.
- The footer input supports in-line editing including backspace and cursor movement keys.
- `--set` values are used directly and skip prompting for those placeholders.
- Placeholder matching supports whitespace: `{{ title }}` and `{{title}}` are equivalent.

## Validation and insertion

- Rendered template content is parsed with `Heading.from_source` before file mutation.
- If parsing fails, capture exits with an error and does not modify files.
- If `parent` is set, the selector must match exactly one heading in the target file.

## Examples

1) Direct template selection

```bash
poetry run org tasks capture quick
```

2) Interactive template selection

```bash
poetry run org tasks capture
```

3) Create a project child heading with generated metadata

```bash
poetry run org tasks capture project-task
```

4) Provide template values through CLI without prompts

```bash
poetry run org tasks capture quick --set title="Draft weekly plan"
```
