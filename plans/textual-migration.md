# Textual Migration Plan

## Recommendation

Use a phased rewrite to Textual.

1. Introduce a shared Textual runtime for interactive commands within the existing command structure.
2. Rewrite `tasks list` first.
3. Rewrite `board`.
4. Rewrite `agenda`.
5. Rewrite `tasks capture` fullscreen placeholder flow last.
6. Remove all obsolete non-Textual interactive code and tests.

That order matches complexity and risk:

- `tasks list` is the simplest and best for proving the shared runtime.
- `board` adds more layout complexity.
- `agenda` adds time-driven refresh and richer row semantics.
- `tasks capture` is currently its own separate input/fullscreen implementation.

This is not a compatibility migration. The goal is to end with one interactive implementation model: Textual.

This rewrite should preserve the existing CLI organization and command nesting. Non-interactive commands should remain available exactly where they are today, including `tasks list` remaining a subcommand of `tasks`.

For each command, the existing CLI surface should be preserved unless there is an explicit decision to change it. That includes:

- command/subcommand names
- CLI switches and arguments
- help text behavior
- config default application and config-driven behavior
- logging and argument handling conventions where they are part of the current command flow

It is acceptable for Textual to become the new app entry point, but that entry point must support the full CLI rather than only the interactive screens. The Textual-based app structure should still expose and run non-interactive commands within the same overall command tree.

## Current Interaction Patterns

Shared patterns in the current code:

- `tasks list`, `board`, and `agenda` already share one fullscreen loop and most input plumbing in `src/org/commands/interactive_common.py`.
- Manual fullscreen loop using Rich `Live(screen=True)`.
- Manual input mode management with `termios` / `tty`.
- Shared key decoding, help modal rendering, mouse toggles, paste handling, prompt editing, and external-action suspension in `src/org/commands/interactive_common.py`.
- In-memory session objects per command with:
  - selection state
  - scroll state
  - search/filter state
  - status message
  - help-modal state
  - active prompt state
  - external-action runner callback
- External blocking actions suspend the screen:
  - editor
  - capture
  - archive-like file mutations
- `tasks capture` is the outlier:
  - separate fullscreen `Live(screen=True)` flow
  - separate `termios` / `tty` handling
  - separate placeholder input loop

This is exactly the kind of code Textual should replace fully rather than wrap.

## Textual Architecture

Do not build separate bespoke apps or split interactive and non-interactive behavior into different top-level applications. Rewrite the existing command implementation in place, using Textual as the application foundation while still supporting the full command tree from the same app entry point.

Recommended structure:

- keep the current CLI and command nesting unchanged
- allow Textual to become the primary app entry point
- ensure the Textual-based app entry point supports both interactive and non-interactive commands
- keep interactive and non-interactive command entrypoints logically in their current command areas even if some wiring moves to the new app entry point
- preserve existing command switches, help text, and config handling for each command
- introduce shared Textual runtime/helpers alongside the existing command code rather than in a separate package
- keep `tasks list` under `src/org/commands/tasks/list/`
- keep `tasks capture` under `src/org/commands/tasks/`
- keep `board` under `src/org/commands/board/`
- keep `agenda` under `src/org/commands/agenda/`

Recommended architectural rules:

- Keep domain logic outside Textual widgets.
- Textual should own:
  - rendering
  - focus
  - key bindings
  - mouse events
  - resize handling
  - modal workflows
  - timers
- Existing command logic should continue to own:
  - task mutation
  - filtering/search semantics
  - reload/preserve-selection logic
  - archive/refile/capture/edit behavior

That means:

- current session dataclasses and mutation/reload helpers remain useful where they still reflect real behavior
- current manual loop/input code is a removal target, not a parallel fallback to keep
- `src/org/commands/interactive_common.py` should not survive as a second interactive runtime once the rewrite is complete

## Shared TUI Design

Recommended shared application concepts across all interactive commands:

- shared app-level action dispatch
- shared external-action suspension/resume
- shared modal lifecycle
- shared command/session mounting within the existing command modules
- command-owned state for selection, search, status, and reload preservation

The app is being rewritten, not reorganized into a new CLI shape. Textual may become the application entry point, but it must support the existing command tree rather than replacing it with an interactive-only application.

For prompt interactions, do not preserve the current footer-editing mechanics as infrastructure.
Use Textual-native interaction:

- small modal input dialog for:
  - search
  - state selection
  - planning timestamp edits
  - refile
  - clock duration
  - capture template selection
- optional inline search only if it materially improves flow

Recommendation:

- Preserve useful prompt semantics where they still make sense.
- Replace manual cursor editing, raw input handling, and footer-specific prompt mechanics with Textual-native prompt flows.
- Do not keep the old prompt implementation in parallel just for compatibility.

## External Action Strategy

Current behavior:

- suspend live screen
- launch editor / capture flow
- resume screen
- refresh state

In Textual, recommend:

- centralize this as an app-level helper
- temporarily suspend the app UI before launching blocking terminal interactions
- resume the app and refresh the screen state afterward

For external editor specifically:

- keep command session state alive
- preserve selection/search/scroll where possible
- show a short status before suspension if useful

## Tasks List

Current behavior:

- vertical selection
- search prompt with live filtering
- state change
- tag edit
- planning edits
- capture prompt
- archive
- external editor
- help modal

Textual recommendation:

- Main screen should be the first full rewrite onto the shared Textual runtime while staying under the existing `tasks list` command path.
- Search, help, and prompts should use Textual-native interaction rather than the shared manual input loop.
- Existing task mutation and reload logic should be reused only where it still fits the new runtime.
- Good first migration target because:
  - single-axis navigation
  - no time-based updates
  - simplest state model

Migration notes:

- reuse current filtering and mutation functions where still appropriate
- remove its old manual interactive path once the Textual rewrite is complete
- remove tests that only assert the old interactive loop/input behavior
- add Textual-based interaction tests for the rewritten command

## Board

Current behavior:

- multi-column board
- horizontal and vertical movement
- variable-height cards/panels
- search filtering
- capture
- archive
- external editor
- state move across columns
- priority changes

Textual recommendation:

- Main widget: board container with one widget per column
- Each column should own a vertical list of cards
- App-level state tracks:
  - selected column
  - selected row within column
- Avoid trying to fake the current Rich panel grid directly
- Better model:
  - custom board widget
  - focus model separate from raw rendered layout

Migration notes:

- rewrite onto the same shared Textual runtime as `tasks list`, without changing the command/module nesting
- likely needs a custom widget rather than stock Textual table/list widgets
- good candidate for virtualization later if columns get large
- Textual should simplify resize behavior a lot here
- remove the old manual interactive board path once complete
- remove tests that only make sense for the deleted manual implementation
- add Textual-based interaction tests

Recommendation:

- preserve keyboard model:
  - arrows for movement
  - shifted arrows for state/priority actions
- consider making focused card visually stronger than today

## Agenda

Current behavior:

- mixed row types:
  - task rows
  - hour markers
  - now marker
  - relative sections
- time-driven refresh for now marker
- date-range paging/scrolling
- task-only actions depending on selected row kind
- capture on timetable-like rows
- refile
- clock duration prompt
- state changes
- planning shifts
- search

Textual recommendation:

- Main widget: custom agenda list/tree-like widget, not plain table
- Model rows explicitly by type
- Make selection row-aware:
  - some rows actionable
  - some rows navigational only
- Use a timer for now-marker refresh
  - `set_interval(60, ...)` or minute-aware scheduling
- Do not keep timeout-based polling to drive refresh once the Textual version exists
- This is the biggest input/runtime benefit Textual brings here

Migration notes:

- keep current row-building/domain logic initially
- move row actions into command handlers that inspect selected row type
- remove the old timeout/event-loop path once the Textual rewrite is complete
- replace old agenda-specific interactive tests with Textual-based tests

Recommendation:

- agenda should be the only screen with timer-driven UI refresh
- this screen most benefits from the migration

## Tasks Capture

Current behavior:

- fullscreen template preview
- placeholder-by-placeholder editing
- inline footer input
- help modal
- custom text input handling

Textual recommendation:

- Treat this as a dedicated form/editor screen inside the shared Textual runtime while keeping it under the existing `tasks capture` command.
- Replace its bespoke `Live(screen=True)` and `termios` / `tty` input loop entirely.
- Use Textual-native input handling rather than preserving raw key-reading code.
- Layout:
  - preview pane/body
  - active field status
  - input widget
- Instead of raw placeholder stepping logic in the footer:
  - use focused input field + preview updates
  - optionally one screen per field or a single form screen with next/prev controls

Migration notes:

- likely simpler after Textual rewrite than today
- but it is sufficiently distinct that it should come after the other commands
- once rewritten, remove the old capture fullscreen/input implementation and its obsolete tests

Recommendation:

- redesign slightly instead of preserving the exact current interaction
- Textual form flow will likely be better than emulating the manual footer editor

## What Gets Replaced

Likely mostly replaced:

- `interactive_common.py` input-mode and terminal-control sections
- shared manual fullscreen event loop
- custom key/input byte decoding
- mouse reporting toggles
- bracketed-paste handling
- help modal rendering helpers tied to the manual runtime
- footer prompt editing mechanics
- the bespoke capture `Live`/raw-input loop

Likely partially retained:

- selection-preservation helpers
- search/filter/mutation helpers
- command-specific session refresh logic

Likely retained as domain logic:

- task mutation functions
- archive/refile/edit/capture integration
- data loading/reload functions
- current render-independent computations

Likely retained as CLI structure:

- one unified application entry point
- current Typer command tree
- current command nesting and subcommand paths
- current non-interactive command availability
- current command switches and arguments
- current command help text behavior
- current command config handling behavior

## Testing Plan

A Textual rewrite changes test style significantly.

Current tests are heavy on:

- pure renderable output
- manual input/runtime helpers
- direct key dispatch against the old event-loop model
- prompt state mutations tied to the old footer-editing flow

Textual plan should add:

- app-level interaction tests using Textual pilot
- screen-specific behavior tests:
  - navigation
  - modal open/close
  - prompt submit/cancel
  - state refresh after mutations
- keep domain/unit tests around current mutation/filter helpers when those helpers still exist and still represent production behavior

Recommended split:

- preserve pure unit tests only for domain/state/data logic that still exists in production
- remove tests that no longer make sense once the old manual runtime is deleted
- add integration-style Textual tests for UI behavior
- avoid carrying old architecture-specific tests forward once the corresponding production code is gone

## Dependency and Tooling Impact

Would entail:

- add `textual` dependency
- likely add test helpers for Textual pilot-based testing
- validate compatibility with current Python target and strict typing setup

Likely no need to replace:

- Typer
- Rich for non-interactive rendering
- current CLI command structure
- current command nesting such as `tasks list`
- current command option/argument surface
- current help text and config-default behavior

## Migration Phases

### Phase 1

- Add Textual dependency
- Create shared Textual runtime architecture inside the existing command layout
- Make the Textual-based app entry point support both interactive and non-interactive commands
- Preserve per-command switches, help text, and config handling while rewiring execution onto the new app foundation
- Define app-level external-action suspend/resume API
- Define shared command mounting and input/action dispatch model

### Phase 2

- Rewrite `tasks list` in Textual
- Keep non-interactive `tasks list` unchanged
- Remove the old interactive implementation for `tasks list`
- Remove tests that only cover the deleted implementation
- Add Textual-based tests

### Phase 3

- Rewrite `board` in Textual
- Remove the old interactive implementation for `board`
- Remove tests that only cover the deleted implementation
- Add Textual-based tests

### Phase 4

- Rewrite `agenda` in Textual
- Add timer-based now-marker refresh
- Remove the old interactive implementation for `agenda`
- Remove tests that only cover the deleted implementation
- Add Textual-based tests

### Phase 5

- Rewrite `tasks capture` in Textual
- Replace manual placeholder loop with Textual form/editor screen
- Remove the old capture fullscreen/input implementation
- Remove tests that only cover the deleted implementation
- Add Textual-based tests

### Phase 6

- Remove obsolete terminal/input plumbing
- Remove remaining Rich `Live` fullscreen helpers no longer used
- Remove obsolete interactive helper code that no longer corresponds to production behavior
- Ensure there are no remaining non-Textual interactive runtime remnants

## Recommendations

1. Rewrite all interactive TUI code in Textual; do not keep the old manual runtime in parallel.
2. Do not start with `agenda`.
3. Do not try to preserve the footer-prompt implementation exactly.
4. Use modal prompts and app-managed timers.
5. Keep the existing CLI organization and command nesting intact, including `tasks list` remaining a subcommand of `tasks`.
6. Remove tests that no longer make sense after the rewrite, and replace them with Textual-based tests.
7. Treat `tasks capture` as a separate UX redesign, not just a port.
8. Keep business logic outside Textual widgets.
9. If Textual becomes the app entry point, it must support non-interactive commands too, not just interactive screens.
10. Preserve each command's switches, help text, and config handling unless there is an explicit decision to change them.

## Open Questions

1. Do you want the Textual TUI to preserve existing key bindings almost exactly, or is some UX cleanup acceptable?
2. Do you want `tasks list` to remain a single-pane list, or should migration be used to add a detail pane?
3. Should `tasks capture` stay placeholder-step-based, or can it become a more form-like editor?
