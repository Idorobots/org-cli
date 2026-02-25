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
- **Function calls**: built-ins like `select(...)`, `sort_by(...)`, `sum`.
- **Operators**: arithmetic, comparison, boolean, membership, regex match.
- **Combinators**: tuple (`,`), variable binding (`as`), pipeline (`|`), fold (`[ ... ]`).

## 3) Syntax reference

### Literals

- `123`, `-3`, `4.5`
- `"text"`
- `true`, `false`
- `none`
- Bare identifiers (for non-function names) are treated as strings.

Examples:

```text
42
"abc"
none
DONE   # equivalent to "DONE"
```

### Variables

Variables are referenced as `$name`.

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
.heading
.properties.priority
```

Bracket field access (dynamic/static key):

```text
.properties["priority"]
.properties[$key]
```

Missing fields resolve to `none`.

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
sort_by(.heading)
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
.todo, .heading
```

### Variable binding

Bind stage output to a variable:

```text
. as $root | $root[]
```

### Fold expression

`[ subquery ]` collects subquery output into a list, per input item.

```text
[ .[] | .heading ]
[]
```

### Pipeline

`left | right` feeds left output stream into right stage.

```text
.[] | select(.todo == "DONE") | .heading
```

## 4) Operator precedence and associativity

Highest to lowest:

1. Postfix access (`.field`, `[]`, `[i]`, `[a:b]`)
2. Power (`**`, right-associative)
3. Multiplicative (`*`, `/`, `mod`, `rem`, `quot`)
4. Additive (`+`, `-`)
5. Comparison (`==`, `!=`, `>`, `<`, `>=`, `<=`, `matches`, `in`)
6. Boolean (`and`, `or`)
7. Tuple (`,`)
8. Binding (`as $name`)
9. Pipeline (`|`)

## 5) Operators reference

Examples below are minimal and syntactically valid. Output is shown as query-value output.

### Equality and comparison

- `==`, `!=`, `>`, `<`, `>=`, `<=`

```text
"b" > "a"             => true
2 <= 2                => true
.todo == "DONE"       => true/false per item
```

### Regex match

- `left matches right` where both operands are strings.

```text
.heading matches "^Fix"   => true/false
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
none or "x" => "x"
```

### Arithmetic

- `**`, `*`, `/`, `+`, `-`, `mod`, `rem`, `quot`

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

### `unique`

- No args.
- Removes duplicate stream values while preserving first occurrence order.

```text
.[] | unique            # [1,1,2,2] => [1,2]
```

### `length`

- No args.
- Emits size for each value (`list`, `tuple`, `dict`, `set`, `string`, org root). Else `none`.

```text
.[] | length            # [[1],"ab",10] => [1,2,none]
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
- Ignores `none` entries.
- For empty collections or all-`none` values returns `none`.

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
- `none` keys are placed last.
- Non-`none` keys must be one comparable category.

```text
.[] | sort_by(.heading)         # ["b","a"] => ["b","a"] (desc)
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
- Emits runtime type name (`none`, `int`, `str`, `OrgNode`, `OrgDate`, ...).

```text
.[] | type             # [none,1,"x"] => ["none","int","str"]
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
  - `timestamp(start, end_or_none)`
  - `timestamp(start, end_or_none, active_or_none)`

```text
timestamp("<2025-01-02 Thu>")
timestamp("<2025-01-02 Thu>", "<2025-01-03 Fri>")
timestamp("<2025-01-02 Thu>", none, false)
# => <2025-01-02 Thu>, <2025-01-02 Thu>--<2025-01-03 Fri>, [2025-01-02 Thu]
```

### `clock(...)`

- Arity: 2 or 3.
- Forms:
  - `clock(start, end)`
  - `clock(start, end, active_or_none)`

```text
clock("<2025-01-02 Thu 10:00>", "<2025-01-02 Thu 11:30>")
# => [2025-01-02 Thu 10:00]--[2025-01-02 Thu 11:30]
```

### `repeated_task(...)`

- Arity: 3 or 4.
- Forms:
  - `repeated_task(timestamp, before_or_none, after_or_none)`
  - `repeated_task(timestamp, before_or_none, after_or_none, active_or_none)`

```text
repeated_task("<2025-01-02 Thu>", "TODO", "DONE")
repeated_task("<2025-01-02 Thu>", none, "DONE", true)
# => [2025-01-02 Thu], <2025-01-02 Thu>
```

## 7) Value model

Runtime values accepted/produced include:

- Scalars: `none`, `bool`, `int`, `float`, `str`
- Collections: `list`, `tuple`, `set`, `dict`
- Org values: `OrgNode`, `OrgRootNode`, `OrgDate`, `OrgDateClock`, `OrgDateRepeatedTask`

```text
# scalar values
none
1
1.5
"abc"
true

# collections
[ .[] | .heading ]
.[0]

# org values
.[] | .scheduled
timestamp("<2025-01-02 Thu>")
```

Notes:

- Missing field access yields `none`.
- Empty org-date fields normalize to `none`.
- Many collection operators/functions require collection inputs and fail on scalars.

## 8) End-to-end examples

```text
# done headings
.[] | select(.todo == "DONE") | .heading

# count children for each top-level node
.[] | .children | length

# collect headings as one list
[ .[] | .heading ]

# use variables in pipeline
. as $root | $root[] | .heading

# dynamic slicing with CLI-provided vars offset/limit
.[ $offset : $offset + $limit ]

# find most recently modified tasks
.[][] | sort_by(.repeated_tasks + .deadline + .closed + .scheduled | max) | .heading
```
