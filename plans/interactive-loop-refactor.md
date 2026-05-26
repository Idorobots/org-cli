# Interactive Loop Refactor Plan

## Goal

Refactor the shared fullscreen interactive commands (`agenda`, `board`, and `tasks list`) to use a single generic `interactive_loop(...)` function, a unified event stream, and command-local event dispatch without action maps or prompt-specific control-flow helpers.

## Scope

Included:

- `src/org/commands/agenda.py`
- `src/org/commands/board.py`
- `src/org/commands/tasks/list.py`
- shared interactive input / loop helpers

Excluded from the first pass:

- `src/org/commands/tasks/capture.py`

`tasks capture` is interactive, but it uses a separate wizard-style flow and should not be forced into the same architecture during this refactor.

## Target Architecture

### Runner

Extract a shared function:

```python
def interactive_loop(
    *,
    render: Callable[[], RenderableType],
    on_event: Callable[[InteractiveEvent], bool],
    run_external: Callable[[Callable[[], None]], None],
    timeout_seconds: float | None = None,
) -> None:
    ...
```

Responsibilities:

- create and manage `Live(..., screen=True, auto_refresh=False)`
- create and manage `InteractiveInputController`
- read the next event with optional timeout
- call `on_event(event)`
- exit when `on_event(...)` returns `False`
- otherwise always re-render with `live.update(render(), refresh=True)`

Non-responsibilities:

- no knowledge of command session/state
- no action-map dispatch
- no prompt handling
- no help modal handling

### Events

Use one shared event union for the fullscreen interactive commands:

```python
type InteractiveEvent = KeypressEvent | InputEvent | TimeoutEvent
```

#### `KeypressEvent`

Represents a single decoded key or control token.

```python
@dataclass(frozen=True)
class KeypressEvent:
    key: str
```

Examples:

- `"q"`
- `"A"`
- `"ENTER"`
- `"ESC"`
- `"BACKSPACE"`
- `"DELETE"`
- `"LEFT"`, `"RIGHT"`, `"UP"`, `"DOWN"`
- `"HOME"`, `"END"`
- `"WHEEL-UP"`, `"WHEEL-DOWN"`
- `"UNSUPPORTED-ESC:..."`
- `"UNSUPPORTED-MOUSE"`

#### `InputEvent`

Represents pasted text input only.

```python
@dataclass(frozen=True)
class InputEvent:
    key: str
```

For paste events, `key` carries the pasted text payload directly.

Commands are responsible for deciding how to merge that text into prompt state.

#### `TimeoutEvent`

Represents an idle timeout tick.

```python
@dataclass(frozen=True)
class TimeoutEvent:
    pass
```

The loop should emit this event explicitly when `timeout_seconds` is provided and no input arrives.

## Input Reader Refactor

Replace the split between `read_keypress()` and `read_input_event()` with one shared low-level reader that returns `InteractiveEvent`.

Requirements:

- read from `sys.stdin.fileno()`
- accept `timeout_seconds: float | None`
- return `TimeoutEvent()` on idle timeout
- return `KeypressEvent(...)` for single key/control input
- return `InputEvent(...)` for bracketed paste payloads
- preserve exact text case for printable keys
- continue decoding wheel / mouse sequences already used today

This reader should become the only input source used by the shared fullscreen interactive commands.

## Command Refactor Shape

Each command should close over its own mutable session state and provide two callbacks:

```python
session = _create_...( ... )

def render() -> RenderableType:
    return _interactive_...(console, session)

def on_event(event: InteractiveEvent) -> bool:
    ...
    return True
```

Then run:

```python
interactive_loop(
    render=render,
    on_event=on_event,
    run_external=run_external,
    timeout_seconds=..., 
)
```

`on_event(...)` becomes the full command state machine.

Recommended event handling order inside each command:

1. help modal mode
2. prompt mode
3. normal command mode
4. timeout handling

## Prompt Refactor

Prompt handling should move entirely into command-local state and event handling.

Replace the current prompt control-flow abstraction with explicit prompt state stored in each session, for example:

```python
@dataclass
class _PromptState:
    label: str
    value: str
    cursor_position: int
    error_message: str
    cancel_status: str
    invalid_status: str
    submit: Callable[[str], None | bool | ActionResultLike]
    preview: Callable[[str], None] | None = None
    cancel: Callable[[], None] | None = None
```

The exact shape can be tuned during implementation, but the command should directly own:

- whether a prompt is active
- prompt text value
- cursor position
- submit/cancel behavior
- preview behavior
- any captured context needed by the prompt

When a prompt is active, `on_event(...)` should:

- insert text for `KeypressEvent` printable keys
- merge pasted text for `InputEvent`
- move cursor on navigation keys
- submit on `ENTER`
- cancel on `ESC`
- apply preview logic after value changes

This removes the separate prompt event loop entirely.

## Direct Command Dispatch

Remove the action-map abstraction for the shared fullscreen commands.

Do not keep compatibility layers such as:

- `_agenda_actions(...)`
- `_flow_board_key_bindings(...)`
- `_tasks_list_actions(...)`
- `dispatch_action_key(...)`
- `action_requires_live_pause(...)`
- `PromptInteractiveAction` / `ExternalInteractiveAction` / `NoninteractiveAction` / `ViewAction`

Instead, each command should dispatch directly inside `on_event(...)` using explicit branching on the event.

Examples:

- `q` / `ESC` return `False`
- movement keys update selection state
- `/` activates a search prompt
- `ENTER` invokes the external editor via `run_external(...)`
- capture/archive/state/tag/planning actions directly mutate session and backing data

This makes the state machine local and explicit.

## External / Fullscreen-Leaving Work

The loop should support temporarily leaving fullscreen for external or terminal-owning work through the provided `run_external(...)` callback.

Expected behavior:

- suspend input controller
- stop live screen
- run callback
- resume live screen
- restore interactive terminal state

Commands should call `run_external(...)` from inside `on_event(...)` when needed for flows such as:

- opening the external editor
- running capture from the fullscreen command

This replaces the current live-pause action metadata and pre-dispatch checks.

## Migration Order

1. Introduce `KeypressEvent`, `InputEvent`, and `TimeoutEvent`.
2. Implement the unified low-level event reader.
3. Extract `interactive_loop(...)`.
4. Convert `tasks list` first.
5. Convert `board`.
6. Convert `agenda`.
7. Remove obsolete shared action / prompt-dispatch abstractions.

## Per-Command Notes

### `tasks list`

Best first target because it has:

- simpler session structure
- no timeout-driven refresh behavior
- enough prompt and external-action behavior to validate the new design

### `board`

Second target because it is structurally close to tasks list but also exercises:

- horizontal and vertical selection movement
- board-specific rendering and scrolling

### `agenda`

Last target because it has extra time-sensitive behavior.

Under the new model:

- `timeout_seconds=1.0`
- idle ticks produce `TimeoutEvent()`
- `on_event(TimeoutEvent())` can refresh minute-sensitive state
- the loop still re-renders unconditionally after the event

## Expected Removals / Simplifications

After migration, the following code should likely be removed or significantly simplified:

- `handle_active_interactive_action_input(...)`
- `dispatch_action_key(...)`
- `action_requires_live_pause(...)`
- old prompt control-flow abstractions in `interactive_actions.py`
- builder wrappers in `interactive_action_builders.py` if no longer used
- duplicated interactive loops in the three command modules

Shared helpers likely worth retaining:

- `InteractiveInputController`
- help modal helpers
- terminal decoding helpers
- small prompt-editing helpers, if they stay generic and minimal

## Design Constraints

- no temporary compatibility layer for old action maps
- no runner knowledge of command session/state
- no prompt-specific runner branch
- unconditional re-render after every handled event
- command callbacks own all state transitions

## Open Implementation Questions

These do not block the plan, but should be settled during coding:

1. Whether prompt state should reuse `FooterPromptState` or replace it with a new command-local prompt dataclass.
2. Whether unsupported mouse/escape sequences should be ignored in the reader or surfaced to commands as explicit `KeypressEvent`s.
3. Whether `tasks capture` should later adopt the unified event reader even if it keeps its bespoke fullscreen flow.
