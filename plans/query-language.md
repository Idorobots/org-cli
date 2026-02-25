# Query Language v2 — Design and Implementation Plan

## 1) Purpose and Scope

Introduce a jq/yq-like query language for `org query` that can select, transform, and filter Org nodes and related values.

### In scope
- Query parser using a parser combinator library (`parsy`)
- AST + compiler to executable query function
- Stream-based execution model
- Operators, forms, values, and built-in functions from the feature spec
- Integration into `org query` command pipeline:
  - load nodes with existing filtering semantics
  - order nodes with existing `--order-by`
  - execute query over ordered stream
  - print results one item per line (or single scalar line)
- Lean parser/executor unit tests (no query command tests yet)

### Out of scope (for now)
- Rich/static type system
- Aggressive syntax recovery
- Exhaustive validation test matrix
- Backward compatibility guarantees for evolving query grammar

---

## 2) High-Level Architecture

## Query execution pipeline
1. Query text (CLI argument)
2. Parse to AST (`parsy`)
3. Compile AST to executable filter function
4. Load/filter/preprocess nodes (existing `load_and_process_data`)
5. Apply ordering (`order_nodes`)
6. Execute compiled query over ordered nodes
7. Render output lines

## Proposed module structure
- `src/org/query_language/__init__.py`
- `src/org/query_language/ast.py`
- `src/org/query_language/parser.py`
- `src/org/query_language/compiler.py`
- `src/org/query_language/runtime.py`
- `src/org/query_language/errors.py`
- `tests/test_query_language_parser.py`
- `tests/test_query_language_runtime.py`

Rationale:
- Keeps parser/AST/runtime isolated from CLI wiring
- Easier to evolve grammar and semantics independently
- Enables focused unit testing without CLI process overhead

---

## 3) Core Design Decisions

## 3.1 Stream-first semantics
Represent query data flow as `list[object]` (stream). Every compiled query stage:
- accepts a stream + evaluation context
- returns a stream

This matches jq-style filter chaining and makes `|`, `.[]`, `select`, and `sort_by` natural.

## 3.2 Missing value behavior
- Missing field access => `None`
- Out-of-bounds index => `None`
- Out-of-bounds slice => `[]` (empty)
- This matches your requested forgiving access model.

## 3.3 Type mismatch behavior
- Operator type mismatches raise query runtime exceptions.
- Comparisons for dates rely on string comparability as requested.
- Validation remains lightweight; strictness can be expanded later.

## 3.4 Variables
Support `$name` lookup from evaluation context.
Initial context supplied by query command:
- `offset`, `limit`
- `todo_keys`, `done_keys`
- optionally future user-provided vars (extensible map)

---

## 4) Language Model

## 4.1 AST (minimum set)
- Forms:
  - `Identity`
  - `Pipe(left, right)`
  - `Comma(left, right)` (or `TupleN(list[Expr])`)
  - `Group(expr)`
  - `FunctionCall(name, arg?)`
  - `Variable(name)`
- Postfix/unary operators:
  - `FieldAccess(expr, field)`
  - `BracketFieldAccess(expr, key_expr)`
  - `Iterate(expr)`
  - `Index(expr, index_expr)`
  - `Slice(expr, start_expr?, end_expr?)`
- Binary operators:
  - `BinaryOp(op, left, right)`
- Literals:
  - `NumberLiteral`
  - `StringLiteral`
  - `BoolLiteral`
  - `NoneLiteral`

## 4.2 Operator precedence (highest -> lowest)
1. Parentheses/grouping
2. Function calls
3. Postfix accessors (`.field`, `["x"]`, `[]`, `[N]`, `[A:B]`)
4. Comparison/membership/matches (`> < >= <= == != matches in`)
5. Boolean (`and`, `or`)
6. Comma (tuple stream composition)
7. Pipe (`|`)

## 4.3 Grammar approach with `parsy`
Use combinator composition + precedence layers:
- `parse_pipe`
- `parse_comma`
- `parse_bool`
- `parse_compare`
- `parse_postfix_chain`
- `parse_primary`

Whitespace parser (`ws`) is threaded between tokens so whitespace is insignificant globally.

---

## 5) Runtime Semantics

## 5.1 Access semantics
For field access on each stream item:
1. `getattr(value, field, MISSING)` for objects
2. dict lookup for mapping-like values
3. fallback `None` for missing

Bracket key (`["field"]` or `[expr]`) supports:
- string key lookup on objects/dicts
- numeric index on sequences
- slice semantics for `[start:end]`
- `[]` expansion to iterate/flatten one level

## 5.2 Binary operator semantics
- `> < >= <=`: numeric-only (or string for date fields if provided as strings)
- `== !=`: structural equality
- `matches`: `re.compile(pattern).match(value)` on strings
- `and or`: boolean operations over truthy/falsy conversion
- `in`: membership (`a in b`) where `b` is collection/string
- If one side yields stream and the other scalar: broadcast scalar.
- If both yield streams: zip-style pairwise application (lean v1 behavior), with clear error for incompatible lengths if needed.

## 5.3 Functions
- `reverse`: reverse sequence/stream
- `unique`: stable dedupe
- `select(subquery)`: keep item when subquery(item) is truthy
- `sort_by(subquery)`: compute per-item key via subquery(item), stable sort

Function registry:
- map function name -> callable implementation
- allows easy additions later

## 5.4 Compiler strategy
Compile AST nodes into Python callables once:
- avoids interpretation overhead per node/item
- keeps hot loop in runtime primitives
- improves performance on large node sets

Signature:
`CompiledExpr = Callable[[list[object], EvalContext], list[object]]`

---

## 6) Query Command Integration Plan

Target file: `src/org/commands/query.py`

## Behavior update
1. Parse query at command start
2. Build compiled executor
3. Load/process nodes with existing shared pipeline (`load_and_process_data`)
4. Apply ordering (`order_nodes`) using existing `--order-by`
5. Execute query against ordered nodes as initial stream
6. Print:
   - if result is collection: one item per line
   - if scalar: one line
   - if empty: `No results`

## Variable context injection
Populate context map with:
- `offset`: `args.offset`
- `limit`: `args.max_results`
- `todo_keys`, `done_keys` from loaded config/inputs

Important design note:
- Do **not** auto-apply offset/max-results slicing in `run_query`; let query expression control slicing (`.[ $offset : $limit ]`) to avoid double limiting and preserve language consistency.

## Error handling
- Parse/runtime errors converted to `typer.BadParameter` with compact message.
- Keep messages practical, not overly defensive.

---

## 7) Performance Plan

- Compile AST once per CLI invocation.
- Keep stream operations list-based and linear-time where possible.
- Avoid repeated regex compilation in `matches` where constant pattern detected (optional small optimization).
- For `sort_by`, compute key once per item and cache locally during sort.
- Prefer iterative transforms over recursive deep traversal in runtime hot paths.

---

## 8) Implementation Steps (Execution Order)

1. Add dependency
   - `parsy` in `pyproject.toml` (`tool.poetry.dependencies`)

2. Create query language package scaffold
   - `src/org/query_language/{__init__,errors,ast,parser,compiler,runtime}.py`

3. Implement core errors and AST
   - lightweight dataclasses + typed literals/operators

4. Implement tokenizer-level primitives with `parsy`
   - identifiers, numbers, strings, booleans, `none`, variables, symbols, keywords, whitespace

5. Implement precedence parser
   - postfix chains first, then binary layers, then comma/pipe

6. Implement compiler
   - transform AST to composable callables

7. Implement runtime primitives
   - stream map/flat-map helpers
   - field/index/slice ops
   - binary op evaluators
   - function registry and implementations

8. Integrate into `run_query`
   - parse/compile
   - load/order nodes
   - execute and print

9. Add lean unit tests (parser + runtime only)
   - no `query` command tests yet

10. Run project validation
   - `poetry run task check`

---

## 9) Validation Plan

## 9.1 Parser sanity tests (`tests/test_query_language_parser.py`)
Cover only representative cases:
- `.todo`
- `.todo == "DONE"`
- `.properties["foo"]`
- `.[0]`
- `.[0:10]`
- `.children[1:2].heading`
- `.[] | reverse`
- `sort_by(.latest_timestamp) | reverse`
- nested/grouped: `select((.dependencies[] | length) == 0)`
- variable refs: `.[$offset:$limit]`, `.todo in $done_keys`
- malformed cases (few): unclosed bracket, bad operator placement

## 9.2 Runtime sanity tests (`tests/test_query_language_runtime.py`)
Using `node_from_org` fixtures:
- identity and field extraction
- missing field returns `None`
- index out of range -> `None`
- slice out of range -> empty list
- select DONE nodes
- sort_by level + reverse
- matches on heading/body
- `in` membership with `$todo_keys`
- tuple/comma behavior
- type mismatch raises error (`"a" > 1`)

## 9.3 Manual smoke validation (post-implementation)
Run examples:
- `org query '.[].repeated_tasks[]'`
- `org query '.[] | select(.todo == "DONE")'`
- `org query '.[$offset:$limit] | .env.filename, .level, .todo, .heading' --offset 10 -n 20`
- and representative select/sort/matches expressions from your list

## 9.4 Quality gates
- `poetry run task check` must pass
- Keep tests lean and focused on language skeleton behavior, not exhaustive correctness matrix

---

## 10) Risks and Mitigations

- Grammar churn risk: encapsulate parser and AST in dedicated package.
- Ambiguous stream-vs-scalar semantics: codify and test broadcasting/zip rules early.
- Runtime type edge cases: fail with explicit query errors; avoid silent coercions.
- Performance regression on large files: compile once, avoid redundant key/regex work.

---

## 11) Deliverables Checklist

- Query parser with `parsy`
- AST + compiler + runtime
- Query command integration in `src/org/commands/query.py`
- Lean parser/runtime tests
- Dependency update for `parsy`
- Passing `poetry run task check`
