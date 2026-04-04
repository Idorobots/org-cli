# Query Language Reference

This document is the reference manual for the `org query` language.

## 1) Mental model: stream processing

A query evaluates over a **stream of values**. Each stage receives a stream and emits a new stream.

- `|` pipes one stage into the next.
- `.` is identity: it forwards the current stream item unchanged.
- Many expressions can emit zero, one, or many output values per input value.

At the CLI, the initial stream contains one value: the loaded roots collection.

```bash
poetry run org query '.[] | .children | length' examples/ARCHIVE_small
```

## 2) What a query is made of

A query is an expression tree composed of these syntax classes:

- **Primary values**: literals, variables, identity, grouped expressions.
- **Postfix accessors**: field access, bracket key/index/slice, iteration.
- **Function calls**: built-ins like `select(...)`, `sort_by(...)`, `sum`, `uuid`.
- **Operators**: arithmetic, comparison, boolean, membership, regex match.
- **Combinators**: tuple (`,`), variable binding (`as`), scoped binding (`let ... in`), conditional (`if ... then ... else ...`), pipeline (`|`), fold (`[ ... ]`).
  sequencing (`;`), dictionary assignment (`=`, limited forms).

## 3) Syntax reference

### Literals

- `123`, `4.5`
- `"text"`
- `true`, `false`
- `null`

Examples:

```text
42
-42
"abc"
null
```

Negative values use unary minus (`-subquery`), which is evaluated as `0 - subquery`.

### Variables

Variables are referenced as `$name`.

Common CLI-provided context variables include `$todo_keys`, `$done_keys`, `$offset`, and `$limit`.

```text
.[] | select(.todo in $done_keys)
```

### Identity and grouping

- `.` returns current value.
- `(expr)` groups by precedence.

```text
.
(.todo == "DONE")
```

### Field access

Dot field access:

```text
.title_text
.properties.priority
```

Bracket field access (dynamic/static key):

```text
.properties["priority"]
.properties[$key]
```

Missing fields resolve to `null`.

### Iteration, index, slice

- Iteration: `expr[]`
- Index: `expr[index_expr]`
- Slice: `expr[start:end]` with optional bounds

```text
.children[]
.[0]
.[1:3]
.[ : $limit ]
```

### Function calls

Known functions can be called with `(...)` when they require arguments.

```text
select(.todo == "DONE")
sort_by(.title_text)
join(",")
```

Some functions are no-arg and are written without parentheses:

```text
reverse
length
sum
```

### Tuple expression

Comma builds tuples from expression outputs:

```text
.todo, .title_text
```

### Variable binding

Bind stage output to a variable:

```text
. as $root | $root[]
```

### Scoped `let` binding

`let <value-subquery> as $name in <body-subquery>` evaluates the value subquery, binds `$name`
while evaluating the body, then restores/clears the variable afterwards.

```text
let .title_text as $h in ("The heading: " + $h)
let "DONE" as $state in select(.todo == $state)
```

### Conditional expression

`if <condition-subquery> then <then-subquery> else <else-subquery>` evaluates the condition and
runs either branch based on truthiness.

`elif` branches are also supported and can repeat:

`if <condition> then <then> elif <condition> then <then> ... else <else>`

```text
2 | if . == 2 then "yes" else "no"
.[] | if .todo == "DONE" then .title_text else "pending"
.[] | if .todo == "DONE" then .title_text elif .todo == "TODO" then "todo" else "pending"
```

### Fold expression

`[ subquery ]` collects subquery output into a list, per input item.

```text
[ .[] | .title_text ]
[]
```

### Dictionary assignment

Assignment is currently supported only for dictionary field writes:

- `<subquery>.field = <value-subquery>`
- `<subquery>[<field-subquery>] = <value-subquery>`

The target subquery must evaluate to dictionaries at runtime. For bracket assignment, the key subquery
must evaluate to a string. Assignment mutates those dictionaries and returns the mutated dictionary
stream.

```text
.properties.done = true
.properties["priority"] = "A"
.properties[$field_name] = "A"
```

No other assignment target forms are supported yet.

### Pipeline

`left | right` feeds left output stream into right stage.

```text
.[] | select(.todo == "DONE") | .title_text
```

### Sequence

`left; right` evaluates `left` for side effects, ignores its output, then evaluates `right` and returns
`right` output.

```text
.properties["seen"] = true; .properties["seen"]
```

## 4) Operator precedence and associativity

Highest to lowest:

1. Postfix access (`.field`, `[]`, `[i]`, `[a:b]`)
2. Power (`**`, right-associative)
3. Unary minus (`-subquery`, evaluated as `0 - subquery`)
4. Multiplicative (`*`, `/`, `mod`, `rem`, `quot`)
5. Additive (`+`, `-`)
6. Comparison (`==`, `!=`, `>`, `<`, `>=`, `<=`, `matches`, `in`)
7. Boolean (`and`, `or`)
8. Tuple (`,`)
9. Binding (`as $name`)
10. Assignment (`=`)
11. Sequence (`;`)
12. Pipeline (`|`)

## 5) Operators reference

Examples below are minimal and syntactically valid. Output is shown as query-value output.

### Equality and comparison

- `==`, `!=`, `>`, `<`, `>=`, `<=`
- Numeric and string operands compare directly.
- When both operands are org date values (`Timestamp`, `Clock`, `Repeat`),
  comparisons use their `start` values.
- For ordering operators with `null`:
  - `a > null`, `a < null`, `null > a`, `null < a` are always `false`
  - `a >= null` and `a <= null` are `true` only when both sides are `null`

```text
"b" > "a"             => true
2 <= 2                => true
.todo == "DONE"       => true/false per item
timestamp("<2025-01-02 Thu>") < clock("<2025-01-03 Fri>", "<2025-01-03 Fri>") => true
timestamp("<2025-01-02 Thu>") > null => false
null <= null => true
1 >= null => false
```

### Regex match

- `left matches right` where both operands are strings.

```text
.title_text matches "^Fix"   => true/false
```

### Membership

- `left in right`
- Right side must be collection-like (`list`, `tuple`, `set`, `dict`, or `string`).

```text
.todo in $done_keys
"a" in "cat"             => true
```

### Boolean

- `and`: returns boolean truthiness conjunction.
- `or`: returns left if left is truthy, else right.

```text
"x" and 1   => true
null or "x" => "x"
```

### Arithmetic

- `**`, `*`, `/`, `+`, `-`, `mod`, `rem`, `quot`
- Unary minus: `-subquery` is evaluated as `0 - subquery`

```text
2 ** 3    => 8
8 / 2     => 4.0
7 mod 3   => 1
-7 rem 3  => -1
-7 quot 3 => -2
```

#### Extended `*`, `+`, `-` behaviors

- `"foo" * 2` => `"foofoo"`
- `"foo" + "bar"` => `"foobar"`
- Collection append/concat: `[1,2] + 3` => `[1,2,3]`, `[1,2] + [3]` => `[1,2,3]`
- Collection subtraction: `[1,2,2,3] - 2` => `[1,3]`, `[1,2,3] - [2,3]` => `[1]`

Collection `+`/`-` preserve left-hand collection type (`list`, `tuple`, `set`).

## 6) Functions reference

### `reverse`

- No args.
- Reverses stream order, or reverses the single collection when stream has exactly one collection item.

```text
reverse                 # [1,2,3] => [3,2,1]
```

### `str(subquery)`

- Converts each subquery result to string.

```text
str(.priority)
```

### `int(subquery)`

- Converts each subquery result to int.
- Accepts integer and string values.

```text
int("42")
```

### `float(subquery)`

- Converts each subquery result to float.
- Accepts float and string values.

```text
float("3.14")
```

### `bool(subquery)`

- Converts each subquery result to bool.
- Accepts boolean and string values (`"true"` / `"false"`, case-insensitive).

```text
bool("true")
```

### `ts(subquery)`

- Converts each subquery result to `Timestamp`.
- Accepts existing org-date values and org timestamp strings.

```text
ts("[2026-03-01 Sun 10:00-12:00]")
```

### `sha256`

- No args.
- Returns a SHA-256 hex digest for each input string value.

```text
"abc" | sha256
```

### `match(subquery)`

- Matches each string input item against regex from subquery.
- Returns `[full_match, group1, group2, ...]` on match, else `null`.

```text
.[] | match("(DONE)-(\\d+)")
```

### `uuid`

- No args.
- Emits a new UUIDv4 string for each input item.

```text
uuid
```

### `debug`

- No args.
- Logs each input value to stdout via the CLI logger and returns values unchanged.

```text
.[] | debug
```

### `unique`

- No args.
- Removes duplicate stream values while preserving first occurrence order.

```text
.[] | unique            # [1,1,2,2] => [1,2]
```

### `length`

- No args.
- Emits size for each value (`list`, `tuple`, `dict`, `set`, `string`, org root). Else `null`.

```text
.[] | length            # [[1],"ab",10] => [1,2,null]
```

### `sum`

- No args.
- Expects collection of numbers.

```text
sum                    # [1,2,3] => 6
```

### `max` / `min`

- No args.
- Expects collection with comparable values of one category (numbers, strings, dates).
- Ignores `null` entries.
- For empty collections or all-`null` values returns `null`.

```text
max                    # [1,9,3] => 9
min                    # ["z","a"] => "a"
```

### `select(condition)`

- Filters items where condition stream has at least one truthy value.

```text
.[] | select(.todo == "DONE")  # emits only DONE items
```

### `sort_by(key_expr)`

- Sorts items by evaluated key in descending order.
- `null` keys are placed last.
- Non-`null` keys must be one comparable category.

```text
.[] | sort_by(.title_text)         # ["b","a"] => ["b","a"] (desc)
```

### `join(separator_expr)`

- Joins collection of items into a string.
- Separator must evaluate to a string.

```text
join(",")              # ["a","b","c"] => "a,b,c"
```

### `map(subquery)`

- Applies subquery to each element of each collection input item.
- Returns one list per input item.

```text
map(. * 2)             # [1,2,3] => [2,4,6]
```

### `type`

- No args.
- Emits runtime type name (`null`, `int`, `str`, `Heading`, `Timestamp`, ...).

```text
.[] | type             # [null,1,"x"] => ["null","int","str"]
```

### `not(condition)`

- Emits boolean negation of condition truthiness per item.

```text
.[] | not(.todo in $done_keys)  # DONE=>false, TODO=>true
```

### `timestamp(...)`

- Arity: 1, 2, or 3.
- Forms:
  - `timestamp(start)`
  - `timestamp(start, end_or_null)`
  - `timestamp(start, end_or_null, active_or_null)`

```text
timestamp("<2025-01-02 Thu>")
timestamp("<2025-01-02 Thu>", "<2025-01-03 Fri>")
timestamp("<2025-01-02 Thu>", null, false)
# => <2025-01-02 Thu>, <2025-01-02 Thu>--<2025-01-03 Fri>, [2025-01-02 Thu]
```

### `clock(...)`

- Arity: 2 or 3.
- Forms:
  - `clock(start, end)`
  - `clock(start, end, active_or_null)`

```text
clock("<2025-01-02 Thu 10:00>", "<2025-01-02 Thu 11:30>")
# => [2025-01-02 Thu 10:00]--[2025-01-02 Thu 11:30]
```

### `repeated_task(...)`

- Arity: 3 or 4.
- Forms:
  - `repeated_task(timestamp, before_or_null, after_or_null)`
  - `repeated_task(timestamp, before_or_null, after_or_null, active_or_null)`

```text
repeated_task("<2025-01-02 Thu>", "TODO", "DONE")
repeated_task("<2025-01-02 Thu>", null, "DONE", true)
# => [2025-01-02 Thu], <2025-01-02 Thu>
```

### `analyze`

- Arity: 0.
- Input: stream of `Heading` values. Any non-`Heading` value (including `Document`) raises a runtime error.
- Output: single `AnalysisResult` value.

Aggregates all nodes in the stream into a complete analysis using default parameters: tag-based category (`"tags"`), no tag remapping, 5 max relations per tag, and `"CATEGORY"` as the category property.

The resulting `AnalysisResult` exposes these fields via dot-access:

| Field | Type | Description |
|---|---|---|
| `.total_tasks` | `int` | Total task count including repeated entries |
| `.unique_tasks` | `int` | Number of unique nodes |
| `.task_states` | `Histogram` | Counts per TODO/DONE/etc. state |
| `.task_categories` | `Histogram` | Counts per `CATEGORY` property value |
| `.task_priorities` | `Histogram` | Counts per priority (A/B/C/none) |
| `.task_days` | `Histogram` | Counts per day of the week |
| `.timerange` | `TimeRange` | Global earliest/latest timestamps |
| `.avg_tasks_per_day` | `float` | Average tasks per day across the time range |
| `.max_single_day_count` | `int` | Peak task count on any single day |
| `.max_repeat_count` | `int` | Highest repeat count for any single task |
| `.tags` | `dict` | Per-tag statistics (`Tag` objects keyed by tag name) |
| `.tag_groups` | `list` | Strongly connected tag groups (`Group` objects) |

```text
# total task count for all nodes
.[][] | analyze | .total_tasks

# top-level priority histogram
.[] | analyze | .task_priorities

# inspect a specific tag
.[][] | analyze | .tags["debugging"]
```

## 7) Value model

Runtime values accepted/produced include:

- Scalars: `null`, `bool`, `int`, `float`, `str`
- Collections: `list`, `tuple`, `set`, `dict`
- Org values: `Heading`, `Document`, `Timestamp`, `Clock`, `Repeat`
- Analysis values: `AnalysisResult`, `Tag`, `Group`, `TimeRange`, `Histogram`

```text
# scalar values
null
1
1.5
"abc"
true

# collections
[ .[] | .title_text ]
.[0]

# org values
.[] | .scheduled
timestamp("<2025-01-02 Thu>")
```

Notes:

- Missing field access yields `null`.
- Empty org-date fields normalize to `null`.
- Many collection operators/functions require collection inputs and fail on scalars.

## 8) End-to-end examples

```text
# done headings
.[] | select(.todo == "DONE") | .title_text

# count children for each top-level node
.[] | .children | length

# collect headings as one list
[ .[] | .title_text ]

# use variables in pipeline
. as $root | $root[] | .title_text

# dynamic slicing with CLI-provided vars offset/limit
.[ $offset : $offset + $limit ]

# find most recently modified tasks
.[][] | sort_by(.repeats + .deadline + .closed + .scheduled | max) | .title_text
```
