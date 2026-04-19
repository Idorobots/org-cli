# Agenda Interactive Actions - Implementation Plan

## 1) Goal

Make `org agenda` interactive with keyboard-driven navigation and edits:

- `f` / `b`: move date window by `--days`
- `n` / `p`: move highlight next/previous task row
- `t`: set TODO state from `heading.document.all_states`
- `Shift+Left` / `Shift+Right`: move highlighted task date by plus/minus 1 day
- `r`: refile highlighted task to another file
- `c`: add clock entry ending now, prompt for duration

Edits must use org-parser mutation and save files immediately. Every edit must be logged.

## 2) Current Baseline

- Agenda rendering/grouping is in `src/org/commands/agenda.py`.
- Mutation/save helpers already exist in `src/org/commands/tasks/common.py`:
  - `load_document(...)`
  - `save_document(...)`
- Refile/update logic exists in `src/org/commands/tasks/update.py` and can be reused/extracted.
- Rendering helpers for state/priority/tags are already shared in `src/org/tui.py`.
- Logging is standardized under logger name `org` (`src/org/logging_config.py`).

## 3) Interaction Model

### 3.1 Screen model

- Keep current table-based agenda rendering.
- Add one highlighted task row at a time.
- Add a compact command/status line below table:
  - `n/p select  f/b span  t state  Shift+Left/Right move date  r refile  c clock  q quit`
- Show last action/error message inline in the status area.

### 3.2 Modes

- **Browse mode**: default; single-key commands active.
- **Prompt mode**: entered by `t`, `r`, `c`; line prompts using console input.
- Return to browse mode after action/cancel.

### 3.3 Non-interactive safety

- If stdout/stdin is not TTY, keep current non-interactive render-and-exit behavior.
- Interactive loop only when TTY (or later optional explicit `--interactive`).

## 4) Internal Architecture

### 4.1 Add session state in `src/org/commands/agenda.py`

Create an `AgendaSession` model with:

- `start_date: date`
- `days: int`
- `args: AgendaArgs`
- `nodes: list[Heading]`
- `rows: list[AgendaRow]` (render model)
- `selectable_row_indexes: list[int]`
- `selected_selectable_idx: int`
- `status_message: str | None`
- `now: datetime`

### 4.2 Build a render model (not render-only)

Introduce `AgendaRow` dataclass:

- `kind`: `hour_marker | now_marker | section | task`
- `day`
- `category`, `time_text`, `task_text`, `tags_text`
- `heading: Heading | None` (for actionable rows)
- `source`: `scheduled | repeat | overdue_scheduled | overdue_deadline | upcoming_deadline | scheduled_untimed`

This provides stable row/task identity for navigation and actions.

### 4.3 Key input adapter

Add a small key-reader abstraction:

- default implementation reads chars/escape sequences from terminal,
- test implementation feeds scripted key events.

Map keys:

- `f`, `b`, `n`, `p`, `t`, `r`, `c`, `q`
- arrows including shifted variants (`\x1b[1;2C`, `\x1b[1;2D`, etc).

## 5) Action Semantics

### 5.1 Span navigation (`f` / `b`)

- `f`: `start_date += timedelta(days=days)`
- `b`: `start_date -= timedelta(days=days)`
- Recompute rows and keep selection by nearest valid task row (fallback first).

### 5.2 Selection (`n` / `p`)

- Move across task rows only.
- Wrap around at ends.

### 5.3 Set state (`t`)

Flow:

1. Get highlighted `Heading`.
2. Show selectable states from `heading.document.all_states`.
3. Set `heading.todo` to selected state.
4. Append repeat/log transition entry:
   - `Repeat(before=<old or None>, after=<new>, timestamp=<now inactive timestamp>)`
5. If `scheduled` or `deadline` has a repeater marker, advance planning date accordingly.
6. Save document and log action.

### 5.4 Move task date (`Shift+Left` / `Shift+Right`)

- Determine target planning field from selected row source:
  - scheduled-like rows -> shift `heading.scheduled`
  - deadline-like rows -> shift `heading.deadline`
- Shift by plus/minus 1 day (preserve time and repeater metadata).
- Save document and log action.

### 5.5 Refile (`r`)

Flow:

1. Resolve current input file list.
2. Prompt for destination using quick shortcuts (`1..N`) or explicit path.
3. Move heading subtree to destination document root.
4. Save source and destination documents.
5. Log source/destination details.

### 5.6 Clock entry (`c`)

Flow:

1. Prompt duration (`H:MM`, plus optional shorthand accepted by parser).
2. Compute end = now; start = now - duration.
3. Build a `Clock` entry (inactive range) and append to `heading.clock_entries`.
4. Save document and log duration/timestamps.

## 6) Mutation and Save Strategy

- All edits are immediate; no global apply step.
- For each edit action:
  - mutate org-parser objects,
  - call `document.sync_heading_id_index()` before save,
  - call `save_document(document)`.
- For refile: save both source and destination.

## 7) Logging Requirements

For each edit action log:

- action name
- file path
- heading title and ID
- before/after values relevant to the action
- for refile: source and destination file
- for clock: start, end, duration

Use `logger = logging.getLogger("org")` in agenda command module.

## 8) Testing Plan

### 8.1 Unit tests (agenda interactivity)

- key decoding (arrows + shifted arrows)
- selection movement and wrap behavior
- forward/backward span movement
- row/source mapping correctness

### 8.2 Action tests with fake interactor

- `t` updates state, appends repeat transition, advances repeater planning dates
- shift-date updates the correct planning field by row source
- `r` moves heading across files and persists both files
- `c` appends valid clock entry ending at mocked now

### 8.3 Non-interactive regression

- Existing agenda tests continue to pass in non-TTY mode.

## 9) Implementation Phases

1. Refactor render pipeline to produce row model + highlighted rendering.
2. Add TTY interactive event loop.
3. Add navigation actions (`f`, `b`, `n`, `p`).
4. Add mutation actions (`t`, shifted arrows, `r`, `c`) with save + logging.
5. Add/expand tests for interactivity and persistence.
6. Update docs in `docs/agenda_command.md` with interactive keys and behavior.
7. Run `poetry run task check`.

## 10) Risks and Mitigations

- Escape sequence differences for shifted arrows:
  - support common CSI variants and show status when unknown.
- Repeater/state transition correctness:
  - centralize date-shift logic and cover with focused tests.
- Selection invalidation after refresh:
  - remap selection by heading identity with nearest-index fallback.
- Cross-file mutation safety:
  - deterministic save order and explicit source/destination logs.

## 11) Open Decision

For `Shift+Left` / `Shift+Right`, move:

1. only the planning field implied by selected row type, or
2. both `SCHEDULED` and `DEADLINE` when both exist.

Recommended default: **(1)** (row-type-driven), to avoid unintended deadline/schedule changes.
