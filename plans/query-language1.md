# Query Language v1 Implementation Plan

## Scope and entry points
- Update `src/org/commands/query.py` to parse/execute the query and print results.
- Add a query language module (suggested: `src/org/query_language.py`) containing tokenizer, parser, AST, and executor.
- Add a lean test file (suggested: `tests/test_query_language.py`) using `tests.conftest.node_from_org` for sanity checks.

## Query language design

### Tokenizer
- Tokens: `.`, identifiers, string literals (double-quoted), numeric literals, `[ ]`, `( )`, `,`, `|`, `:`, operators (`> < >= <= == != matches`), `$`-variables, and keywords (`select`, `sort_by`, `reverse`, `unique`).
- Skip whitespace; allow compact expressions like `.children[0].todo`.

### AST nodes
- Filters: `Identity`, `FieldAccess(name)`, `BracketFieldAccess(name)`, `Index(n)`, `Slice(start, end)`, `Iterate`, `Pipe(left, right)`, `Comma(left, right)`, `Select(condition)`, `SortBy(inner)`, `Function(name)`.
- Expressions: `Literal(value)`, `Variable(name)`, `Comparison(op, left, right)`.

### Grammar (recursive descent)
- `pipeline := comma ('|' comma)*`
- `comma := filter (',' filter)*`
- `filter := primary (postfix)*`
- `primary := '.' | function | select | sort_by | '(' pipeline ')'`
- `postfix := field | bracket_field | iterate | index | slice`
- `select := 'select' '(' condition ')'`
- `sort_by := 'sort_by' '(' pipeline ')'`
- `condition := pipeline (op pipeline)?` (allow truthy check when no operator)

### Validation
- Keep light; only enforce token/structure correctness and required delimiters.
- Raise a dedicated `QueryError` with user-facing messages.

## Execution model

### Compile and run
- Compile the AST into a callable `executor(nodes: list[OrgNode], variables: dict[str, object]) -> object`.
- Stream is represented as `list[object]`; each filter consumes a stream and returns a stream.

### Filter behavior
- `.`: returns stream unchanged.
- `.field` / `.["field"]`: for each value in stream, resolve `field`:
  - `getattr(value, field)` if present, else `value[field]` for dict-like values.
  - Raise `QueryError` if missing.
- `.[]`: for each value, iterate lists/tuples/sets; flatten into a single stream. Raise on non-iterables.
- `.[N]`: index into list/tuple; raise on non-indexable or out of range.
- `.[A:B]`: slice list/tuple; support missing A/B; raise on non-sliceable.
- `,`: evaluate both filters on the same input item and return a tuple of single results per input.
- `|`: feed left stream into right.
- `select(...)`: evaluate condition per input; keep input when condition is truthy/`True`.
- `sort_by(...)`: evaluate inner query per input to obtain a key and sort the stream by that key.
- `reverse`: reverse list/tuple stream (or if stream is a single list, reverse that list).
- `unique`: de-duplicate while preserving order.

### Operators
- Numeric comparisons: `>`, `<`, `>=`, `<=` require numeric types; raise `QueryError` on mismatch.
- Equality: `==`, `!=` perform structural equality.
- `matches`: require strings and use `re.compile(pattern).match(value)`.

### Variables
- Support `$offset` and `$limit` only, injected from CLI args.

## Update query command
- In `run_query`:
  - Load nodes via `load_and_process_data` and order via `order_nodes`.
  - Build executor from `args.query`.
  - Execute with `variables={"offset": args.offset, "limit": args.max_results}`.
  - Print results:
    - If result is list/tuple: print each item on its own line.
    - If result is scalar: print once.
    - Use `str(value).rstrip()` for `OrgNode` to avoid trailing newlines.
  - Catch `QueryError` and re-raise as `typer.BadParameter` with a clear message.

## Tests (lean sanity checks)
- Use `node_from_org` to generate predictable OrgNode trees.
- Minimal coverage targets:
  - `.[] | select(.todo == "DONE")` filters DONE nodes.
  - `.children[0].todo` returns expected todo.
  - `.children | reverse | .[0]` returns last child.
  - `.children | sort_by(.heading) | .[0].heading` works.
  - `matches` operator works on headings.
  - Slice with variables: `.[ $offset : $limit ]` on a list.
- Keep tests small and focused; no CLI tests.

## Performance considerations
- Use list comprehensions and avoid deep recursion in execution.
- Keep AST evaluation iterative where possible.
- Avoid converting large lists repeatedly; use in-place operations for `reverse` when safe.
