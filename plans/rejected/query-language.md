# Query Language Implementation Plan

## Overview

This plan outlines the implementation of a jq-style query language for the org-cli tool. The query language will allow users to select, filter, and transform Org-mode nodes and their properties using a declarative syntax.

**Goal:** Enable flexible querying of Org-mode data structures without writing custom Python code.

**Target Invocations:**
```bash
org query '.[].repeated_tasks[]'
org query '.[] | select(.todo == "DONE")'
org query '.[$offset : $limit] | .env.filename, .level, .todo, .heading'
org query '.children | reverse | .[0]'
```

## Architecture

### High-Level Design

```
Query String → Parser → AST → Compiler → Executor → Results
     ↓                                        ↓
  Validation                            Apply to Nodes
```

**Components:**
1. **Parser**: Tokenizes and parses query strings into an Abstract Syntax Tree (AST)
2. **AST**: Represents the query structure using Python dataclasses
3. **Compiler**: Validates the AST and prepares execution plan
4. **Executor**: Applies the query to input data and produces results
5. **Formatter**: Renders results for console output

### Module Structure

```
src/org/query/
├── __init__.py         # Public API exports
├── ast.py              # AST node definitions
├── parser.py           # Query string parser
├── executor.py         # Query execution engine
├── exceptions.py       # Custom exceptions
└── formatter.py        # Result formatting

tests/query/
├── test_parser.py      # Parser unit tests
├── test_executor.py    # Executor unit tests
└── test_integration.py # End-to-end query tests
```

## Query Language Specification

### Forms

| Form | Description | Example | Result |
|------|-------------|---------|--------|
| `.` | Identity | `.` | Input unchanged |
| `.field` | Field access | `.heading` | Node's heading |
| `.["field"]` | Bracket field access | `.["heading"]` | Node's heading |
| `.[]` | Iterate collection | `.[]` | Each item |
| `.[N]` | Index access | `.[0]` | First item |
| `.[N:M]` | Slice | `.[2:5]` | Items 2, 3, 4 |
| `,` | Combine (tuple) | `.todo, .heading` | Tuple of values |
| `|` | Pipe | `.children | .[0]` | First child |

### Functions

| Function | Description | Example | Result |
|----------|-------------|---------|--------|
| `reverse` | Reverse collection | `.children \| reverse` | Reversed list |
| `unique` | Remove duplicates | `.tags \| unique` | Unique tags |
| `select(expr)` | Filter by condition | `select(.todo == "DONE")` | Filtered items |
| `sort_by(expr)` | Sort by expression | `sort_by(.level)` | Sorted list |

### Operators

| Operator | Description | Type | Example |
|----------|-------------|------|---------|
| `>` | Greater than | Numeric | `.level > 2` |
| `<` | Less than | Numeric | `.level < 5` |
| `>=` | Greater or equal | Numeric | `.level >= 1` |
| `<=` | Less or equal | Numeric | `.level <= 3` |
| `==` | Equality | Any | `.todo == "DONE"` |
| `!=` | Inequality | Any | `.todo != "TODO"` |
| `matches` | Regex match | String | `.heading matches "bug"` |

### Supported Data Types

**OrgNode Fields:**
- `heading`: str | None
- `todo`: str | None
- `tags`: set[str]
- `level`: int | None
- `body`: str
- `children`: list[OrgNode]
- `repeated_tasks`: list[OrgDateRepeatedTask]
- `env`: OrgEnv (has `filename`, `todo_keys`, `done_keys`)
- Properties via `get_property(name)` - to be addressed in future extension

**OrgDateRepeatedTask Fields:**
- `start`: datetime | None
- `after`: str (todo state after completion)

**Collections:**
- Lists, tuples, sets (iterable)
- Strings (for regex matching)
- Numbers (for comparisons)

## Implementation Phases

### Phase 1: AST Definitions (1-2 hours)

**File:** `src/org/query/ast.py`

Define dataclasses for AST nodes:

```python
@dataclass
class QueryNode:
    """Base class for all AST nodes."""
    pass

@dataclass
class Identity(QueryNode):
    """Represents '.' - returns input unchanged."""
    pass

@dataclass
class FieldAccess(QueryNode):
    """Represents '.field' or '.["field"]'."""
    field: str

@dataclass
class IndexAccess(QueryNode):
    """Represents '.[N]'."""
    index: int

@dataclass
class SliceAccess(QueryNode):
    """Represents '.[N:M]'."""
    start: int | None
    stop: int | None

@dataclass
class Iterator(QueryNode):
    """Represents '.[]' - iterate over collection."""
    pass

@dataclass
class Pipe(QueryNode):
    """Represents 'expr | expr' - chain filters."""
    left: QueryNode
    right: QueryNode

@dataclass
class Tuple(QueryNode):
    """Represents 'expr, expr' - combine into tuple."""
    expressions: list[QueryNode]

@dataclass
class FunctionCall(QueryNode):
    """Represents function calls like 'reverse', 'select(...)'."""
    name: str
    args: list[QueryNode]

@dataclass
class Comparison(QueryNode):
    """Represents comparison operations."""
    operator: str  # '>', '<', '>=', '<=', '==', '!=', 'matches'
    left: QueryNode
    right: QueryNode

@dataclass
class Literal(QueryNode):
    """Represents literal values (strings, numbers)."""
    value: str | int | float
```

**Deliverables:**
- AST node definitions
- Type hints for all nodes
- Docstrings explaining each node type

### Phase 2: Parser Implementation (3-4 hours)

**File:** `src/org/query/parser.py`

Implement a recursive descent parser:

```python
class QueryParser:
    """Parse query strings into AST."""
    
    def __init__(self, query: str):
        self.query = query
        self.pos = 0
        self.tokens = self._tokenize(query)
        self.current = 0
    
    def parse(self) -> QueryNode:
        """Parse the query string into an AST."""
        return self._parse_pipe()
    
    def _tokenize(self, query: str) -> list[Token]:
        """Tokenize the query string."""
        # Regex-based tokenizer
        # Tokens: DOT, FIELD, LBRACKET, RBRACKET, PIPE, COMMA, etc.
        pass
    
    def _parse_pipe(self) -> QueryNode:
        """Parse pipe expressions (lowest precedence)."""
        left = self._parse_tuple()
        while self._match('|'):
            right = self._parse_tuple()
            left = Pipe(left, right)
        return left
    
    def _parse_tuple(self) -> QueryNode:
        """Parse tuple expressions."""
        exprs = [self._parse_comparison()]
        while self._match(','):
            exprs.append(self._parse_comparison())
        return Tuple(exprs) if len(exprs) > 1 else exprs[0]
    
    def _parse_comparison(self) -> QueryNode:
        """Parse comparison expressions."""
        left = self._parse_function()
        if self._match_any(['>', '<', '>=', '<=', '==', '!=', 'matches']):
            op = self._previous()
            right = self._parse_function()
            return Comparison(op, left, right)
        return left
    
    def _parse_function(self) -> QueryNode:
        """Parse function calls."""
        if self._check_function():
            name = self._advance()
            args = []
            if name in ['select', 'sort_by']:
                self._expect('(')
                args = [self._parse_pipe()]
                self._expect(')')
            return FunctionCall(name, args)
        return self._parse_primary()
    
    def _parse_primary(self) -> QueryNode:
        """Parse primary expressions (field access, literals, etc.)."""
        if self._match('.'):
            return self._parse_field_or_index()
        if self._match_string():
            return Literal(self._string_value())
        if self._match_number():
            return Literal(self._number_value())
        raise ParseError(f"Unexpected token at position {self.current}")
    
    def _parse_field_or_index(self) -> QueryNode:
        """Parse field access, index, slice, or iterator."""
        if self._match('['):
            return self._parse_bracket_access()
        if self._match_identifier():
            return FieldAccess(self._previous())
        return Identity()
    
    def _parse_bracket_access(self) -> QueryNode:
        """Parse bracket notation: .[N], .[N:M], .[], .["field"]."""
        if self._match(']'):
            return Iterator()
        if self._match_string():
            field = self._string_value()
            self._expect(']')
            return FieldAccess(field)
        # Handle slice or index
        start = self._parse_number() if self._check_number() else None
        if self._match(':'):
            stop = self._parse_number() if self._check_number() else None
            self._expect(']')
            return SliceAccess(start, stop)
        self._expect(']')
        return IndexAccess(start) if start is not None else Iterator()
```

**Key Design Decisions:**
- Use regex-based tokenization for simplicity
- Recursive descent parsing for readability
- Not overly defensive - basic validation only
- Clear error messages for parse failures

**Deliverables:**
- `QueryParser` class
- Tokenization logic
- Parsing methods for all forms
- Basic error handling with line/column info
- Unit tests for parser

### Phase 3: Executor Implementation (3-4 hours)

**File:** `src/org/query/executor.py`

Implement query execution:

```python
class QueryExecutor:
    """Execute parsed queries against data."""
    
    def execute(self, ast: QueryNode, data: Any) -> Any:
        """Execute the query AST against input data."""
        if isinstance(ast, Identity):
            return self._execute_identity(data)
        if isinstance(ast, FieldAccess):
            return self._execute_field_access(ast, data)
        if isinstance(ast, IndexAccess):
            return self._execute_index_access(ast, data)
        if isinstance(ast, SliceAccess):
            return self._execute_slice_access(ast, data)
        if isinstance(ast, Iterator):
            return self._execute_iterator(data)
        if isinstance(ast, Pipe):
            return self._execute_pipe(ast, data)
        if isinstance(ast, Tuple):
            return self._execute_tuple(ast, data)
        if isinstance(ast, FunctionCall):
            return self._execute_function(ast, data)
        if isinstance(ast, Comparison):
            return self._execute_comparison(ast, data)
        if isinstance(ast, Literal):
            return ast.value
        raise ExecutionError(f"Unknown AST node type: {type(ast)}")
    
    def _execute_identity(self, data: Any) -> Any:
        """Return data unchanged."""
        return data
    
    def _execute_field_access(self, ast: FieldAccess, data: Any) -> Any:
        """Access a field on an object."""
        if not hasattr(data, ast.field):
            raise ExecutionError(
                f"Field '{ast.field}' not found on {type(data).__name__}"
            )
        return getattr(data, ast.field)
    
    def _execute_index_access(self, ast: IndexAccess, data: Any) -> Any:
        """Access an item by index."""
        try:
            if isinstance(data, set):
                data = list(data)
            return data[ast.index]
        except (IndexError, TypeError) as e:
            raise ExecutionError(f"Index access failed: {e}")
    
    def _execute_slice_access(self, ast: SliceAccess, data: Any) -> Any:
        """Access a slice of a collection."""
        try:
            if isinstance(data, set):
                data = list(data)
            return data[ast.start:ast.stop]
        except TypeError as e:
            raise ExecutionError(f"Slice access failed: {e}")
    
    def _execute_iterator(self, data: Any) -> list[Any]:
        """Iterate over a collection, returning a list of items."""
        try:
            if isinstance(data, (list, tuple)):
                return list(data)
            if isinstance(data, set):
                return list(data)
            return list(data)
        except TypeError as e:
            raise ExecutionError(f"Cannot iterate over {type(data).__name__}: {e}")
    
    def _execute_pipe(self, ast: Pipe, data: Any) -> Any:
        """Execute left side, then pass result to right side."""
        intermediate = self.execute(ast.left, data)
        # If intermediate is a list, apply right to each element
        if isinstance(intermediate, list):
            return [self.execute(ast.right, item) for item in intermediate]
        return self.execute(ast.right, intermediate)
    
    def _execute_tuple(self, ast: Tuple, data: Any) -> tuple[Any, ...]:
        """Execute each expression and return as tuple."""
        return tuple(self.execute(expr, data) for expr in ast.expressions)
    
    def _execute_function(self, ast: FunctionCall, data: Any) -> Any:
        """Execute a function call."""
        if ast.name == 'reverse':
            return self._function_reverse(data)
        if ast.name == 'unique':
            return self._function_unique(data)
        if ast.name == 'select':
            return self._function_select(ast.args[0], data)
        if ast.name == 'sort_by':
            return self._function_sort_by(ast.args[0], data)
        raise ExecutionError(f"Unknown function: {ast.name}")
    
    def _function_reverse(self, data: Any) -> list[Any]:
        """Reverse a collection."""
        if not isinstance(data, (list, tuple, set)):
            raise ExecutionError(f"Cannot reverse {type(data).__name__}")
        if isinstance(data, set):
            data = list(data)
        return list(reversed(data))
    
    def _function_unique(self, data: Any) -> list[Any]:
        """Remove duplicates while preserving order."""
        if not isinstance(data, (list, tuple)):
            raise ExecutionError(f"Cannot unique {type(data).__name__}")
        seen = set()
        result = []
        for item in data:
            # Use string representation for unhashable types
            key = str(item) if not isinstance(item, (str, int, float)) else item
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result
    
    def _function_select(self, condition: QueryNode, data: Any) -> list[Any]:
        """Filter items where condition evaluates to truthy."""
        if not isinstance(data, (list, tuple)):
            raise ExecutionError("select() requires a list")
        result = []
        for item in data:
            try:
                if self.execute(condition, item):
                    result.append(item)
            except ExecutionError:
                # Skip items that fail condition evaluation
                continue
        return result
    
    def _function_sort_by(self, key_expr: QueryNode, data: Any) -> list[Any]:
        """Sort collection by key expression."""
        if not isinstance(data, (list, tuple)):
            raise ExecutionError("sort_by() requires a list")
        
        def sort_key(item: Any) -> Any:
            try:
                return self.execute(key_expr, item)
            except ExecutionError:
                return None  # Sort None values last
        
        # Sort with None values last
        return sorted(data, key=lambda x: (sort_key(x) is None, sort_key(x)))
    
    def _execute_comparison(self, ast: Comparison, data: Any) -> bool:
        """Execute a comparison operation."""
        left_val = self.execute(ast.left, data)
        right_val = self.execute(ast.right, data)
        
        if ast.operator == '==':
            return left_val == right_val
        if ast.operator == '!=':
            return left_val != right_val
        if ast.operator == 'matches':
            return self._matches(left_val, right_val)
        
        # Numeric comparisons
        if not isinstance(left_val, (int, float)) or not isinstance(right_val, (int, float)):
            raise ExecutionError(
                f"Operator '{ast.operator}' requires numeric operands, "
                f"got {type(left_val).__name__} and {type(right_val).__name__}"
            )
        
        if ast.operator == '>':
            return left_val > right_val
        if ast.operator == '<':
            return left_val < right_val
        if ast.operator == '>=':
            return left_val >= right_val
        if ast.operator == '<=':
            return left_val <= right_val
        
        raise ExecutionError(f"Unknown operator: {ast.operator}")
    
    def _matches(self, text: Any, pattern: Any) -> bool:
        """Execute regex match."""
        if not isinstance(text, str) or not isinstance(pattern, str):
            raise ExecutionError(
                f"'matches' requires string operands, "
                f"got {type(text).__name__} and {type(pattern).__name__}"
            )
        try:
            import re
            return bool(re.compile(pattern).search(text))
        except re.error as e:
            raise ExecutionError(f"Invalid regex pattern: {e}")
```

**Key Design Decisions:**
- Pipe operator flattens results when operating on lists
- Functions operate on collections, not individual items
- select() silently skips items that fail condition evaluation
- Type mismatches raise clear ExecutionError exceptions
- None values in sort_by() are placed at the end

**Deliverables:**
- `QueryExecutor` class
- Execution methods for all AST nodes
- Function implementations
- Operator implementations
- Error handling with context
- Unit tests for executor

### Phase 4: Exception Handling (1 hour)

**File:** `src/org/query/exceptions.py`

Define custom exceptions:

```python
class QueryError(Exception):
    """Base exception for query-related errors."""
    pass

class ParseError(QueryError):
    """Raised when query parsing fails."""
    
    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        if self.position is not None:
            return f"Parse error at position {self.position}: {self.message}"
        return f"Parse error: {self.message}"

class ExecutionError(QueryError):
    """Raised when query execution fails."""
    
    def __init__(self, message: str, context: str | None = None):
        self.message = message
        self.context = context
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        if self.context:
            return f"Execution error in {self.context}: {self.message}"
        return f"Execution error: {self.message}"
```

**Deliverables:**
- Exception class definitions
- Formatted error messages
- Context tracking for better debugging

### Phase 5: Result Formatter (1 hour)

**File:** `src/org/query/formatter.py`

Format query results for console output:

```python
def format_result(result: Any) -> str:
    """Format a single result value for output."""
    if isinstance(result, orgparse.node.OrgNode):
        # Return full node representation
        return str(result).rstrip()
    if isinstance(result, (list, tuple)):
        # Format each item on a separate line
        return '\n'.join(format_result(item) for item in result)
    if isinstance(result, set):
        # Convert to sorted list for consistent output
        return '\n'.join(format_result(item) for item in sorted(result))
    if result is None:
        return ""
    # Default: string representation
    return str(result)

def format_results(results: Any) -> list[str]:
    """Format query results into a list of output lines."""
    if isinstance(results, (list, tuple)):
        return [format_result(item) for item in results]
    return [format_result(results)]
```

**Deliverables:**
- Result formatting functions
- Handling of different result types
- Consistent output formatting

### Phase 6: Integration with Query Command (2 hours)

**File:** `src/org/commands/query.py`

Update the query command to use the new query language:

```python
from org.query import QueryParser, QueryExecutor, QueryError, format_results

def run_query(args: QueryArgs) -> None:
    """Run the query command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled)
    order_by = normalize_order_by(args.order_by)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    
    # Parse the query
    try:
        parser = QueryParser(args.query)
        ast = parser.parse()
    except QueryError as e:
        console.print(f"[red]Query parse error:[/red] {e}", markup=True)
        raise typer.Exit(1)
    
    # Load and filter nodes
    with processing_status(console, color_enabled):
        nodes, _todo_keys, _done_keys = load_and_process_data(args)
        if order_by and nodes:
            nodes = order_nodes(nodes, order_by)
    
    # Execute the query
    try:
        executor = QueryExecutor()
        results = executor.execute(ast, nodes)
    except QueryError as e:
        console.print(f"[red]Query execution error:[/red] {e}", markup=True)
        raise typer.Exit(1)
    
    # Format and display results
    output_lines = format_results(results)
    if not output_lines or all(not line for line in output_lines):
        console.print("No results", markup=False)
        return
    
    for line in output_lines:
        if line:
            console.print(line, markup=False)
```

**Key Changes:**
1. Parse query string into AST
2. Execute AST against filtered/ordered nodes
3. Format results for display
4. Handle errors gracefully with Typer

**Deliverables:**
- Updated `run_query()` function
- Error handling integration
- Result formatting integration

### Phase 7: Testing (2-3 hours)

#### Parser Tests (`tests/query/test_parser.py`)

```python
def test_parse_identity():
    """Test parsing identity operator."""
    parser = QueryParser('.')
    ast = parser.parse()
    assert isinstance(ast, Identity)

def test_parse_field_access():
    """Test parsing field access."""
    parser = QueryParser('.heading')
    ast = parser.parse()
    assert isinstance(ast, FieldAccess)
    assert ast.field == 'heading'

def test_parse_index_access():
    """Test parsing index access."""
    parser = QueryParser('.[0]')
    ast = parser.parse()
    assert isinstance(ast, IndexAccess)
    assert ast.index == 0

def test_parse_slice_access():
    """Test parsing slice access."""
    parser = QueryParser('.[2:5]')
    ast = parser.parse()
    assert isinstance(ast, SliceAccess)
    assert ast.start == 2
    assert ast.stop == 5

def test_parse_iterator():
    """Test parsing iterator."""
    parser = QueryParser('.[]')
    ast = parser.parse()
    assert isinstance(ast, Iterator)

def test_parse_pipe():
    """Test parsing pipe operator."""
    parser = QueryParser('.children | .[0]')
    ast = parser.parse()
    assert isinstance(ast, Pipe)

def test_parse_tuple():
    """Test parsing tuple."""
    parser = QueryParser('.todo, .heading')
    ast = parser.parse()
    assert isinstance(ast, Tuple)
    assert len(ast.expressions) == 2

def test_parse_function_reverse():
    """Test parsing reverse function."""
    parser = QueryParser('.children | reverse')
    ast = parser.parse()
    assert isinstance(ast, Pipe)
    assert isinstance(ast.right, FunctionCall)
    assert ast.right.name == 'reverse'

def test_parse_function_select():
    """Test parsing select function."""
    parser = QueryParser('select(.todo == "DONE")')
    ast = parser.parse()
    assert isinstance(ast, FunctionCall)
    assert ast.name == 'select'
    assert len(ast.args) == 1

def test_parse_comparison():
    """Test parsing comparisons."""
    parser = QueryParser('.level > 2')
    ast = parser.parse()
    assert isinstance(ast, Comparison)
    assert ast.operator == '>'

def test_parse_invalid_query():
    """Test that invalid queries raise ParseError."""
    with pytest.raises(ParseError):
        parser = QueryParser('.[')
        parser.parse()
```

#### Executor Tests (`tests/query/test_executor.py`)

```python
def test_execute_identity():
    """Test identity returns input unchanged."""
    executor = QueryExecutor()
    ast = Identity()
    assert executor.execute(ast, 42) == 42

def test_execute_field_access():
    """Test field access on OrgNode."""
    node = create_test_node(heading="Test")
    executor = QueryExecutor()
    ast = FieldAccess('heading')
    assert executor.execute(ast, node) == "Test"

def test_execute_index_access():
    """Test index access on list."""
    executor = QueryExecutor()
    ast = IndexAccess(1)
    assert executor.execute(ast, [10, 20, 30]) == 20

def test_execute_slice_access():
    """Test slice access on list."""
    executor = QueryExecutor()
    ast = SliceAccess(1, 3)
    assert executor.execute(ast, [10, 20, 30, 40]) == [20, 30]

def test_execute_iterator():
    """Test iterator on list."""
    executor = QueryExecutor()
    ast = Iterator()
    result = executor.execute(ast, [1, 2, 3])
    assert result == [1, 2, 3]

def test_execute_pipe():
    """Test pipe operator."""
    executor = QueryExecutor()
    ast = Pipe(Iterator(), IndexAccess(0))
    assert executor.execute(ast, [10, 20, 30]) == [10]

def test_execute_tuple():
    """Test tuple execution."""
    node = create_test_node(heading="Test", todo="DONE")
    executor = QueryExecutor()
    ast = Tuple([FieldAccess('heading'), FieldAccess('todo')])
    assert executor.execute(ast, node) == ("Test", "DONE")

def test_execute_reverse():
    """Test reverse function."""
    executor = QueryExecutor()
    ast = FunctionCall('reverse', [])
    assert executor.execute(ast, [1, 2, 3]) == [3, 2, 1]

def test_execute_unique():
    """Test unique function."""
    executor = QueryExecutor()
    ast = FunctionCall('unique', [])
    assert executor.execute(ast, [1, 2, 2, 3, 1]) == [1, 2, 3]

def test_execute_select():
    """Test select function."""
    nodes = [
        create_test_node(todo="TODO"),
        create_test_node(todo="DONE"),
        create_test_node(todo="TODO"),
    ]
    executor = QueryExecutor()
    condition = Comparison('==', FieldAccess('todo'), Literal("DONE"))
    ast = FunctionCall('select', [condition])
    result = executor.execute(ast, nodes)
    assert len(result) == 1
    assert result[0].todo == "DONE"

def test_execute_sort_by():
    """Test sort_by function."""
    nodes = [
        create_test_node(level=3),
        create_test_node(level=1),
        create_test_node(level=2),
    ]
    executor = QueryExecutor()
    ast = FunctionCall('sort_by', [FieldAccess('level')])
    result = executor.execute(ast, nodes)
    assert [n.level for n in result] == [1, 2, 3]

def test_execute_comparison_equality():
    """Test equality comparison."""
    node = create_test_node(todo="DONE")
    executor = QueryExecutor()
    ast = Comparison('==', FieldAccess('todo'), Literal("DONE"))
    assert executor.execute(ast, node) is True

def test_execute_comparison_numeric():
    """Test numeric comparison."""
    node = create_test_node(level=5)
    executor = QueryExecutor()
    ast = Comparison('>', FieldAccess('level'), Literal(2))
    assert executor.execute(ast, node) is True

def test_execute_comparison_matches():
    """Test regex matches."""
    node = create_test_node(heading="Fix bug in parser")
    executor = QueryExecutor()
    ast = Comparison('matches', FieldAccess('heading'), Literal("bug"))
    assert executor.execute(ast, node) is True

def test_execute_field_not_found():
    """Test error when field doesn't exist."""
    node = create_test_node()
    executor = QueryExecutor()
    ast = FieldAccess('nonexistent')
    with pytest.raises(ExecutionError, match="Field 'nonexistent' not found"):
        executor.execute(ast, node)

def test_execute_type_mismatch():
    """Test error on type mismatch in comparison."""
    node = create_test_node(heading="Test")
    executor = QueryExecutor()
    ast = Comparison('>', FieldAccess('heading'), Literal(5))
    with pytest.raises(ExecutionError, match="requires numeric operands"):
        executor.execute(ast, node)
```

**Test Coverage Goals:**
- Parser: ~70% (basic sanity checks)
- Executor: ~70% (core functionality)
- Integration: ~50% (end-to-end examples)

**Deliverables:**
- Parser unit tests
- Executor unit tests
- Test fixtures for OrgNode creation
- Clear test names and documentation

## Examples

### Example 1: Get all repeated tasks

```bash
org query '.[].repeated_tasks[]' examples/ARCHIVE_small
```

**Query breakdown:**
1. `.[]` - Iterate over all nodes
2. `.repeated_tasks` - Access repeated_tasks field
3. `[]` - Iterate over repeated tasks

### Example 2: Filter completed tasks

```bash
org query '.[] | select(.todo == "DONE")' examples/ARCHIVE_small
```

**Query breakdown:**
1. `.[]` - Iterate over all nodes
2. `|` - Pipe to next filter
3. `select(.todo == "DONE")` - Keep only DONE tasks

### Example 3: Extract specific fields

```bash
org query '.[] | .env.filename, .level, .todo, .heading' examples/ARCHIVE_small
```

**Query breakdown:**
1. `.[]` - Iterate over all nodes
2. `|` - Pipe to next filter
3. `.env.filename, .level, .todo, .heading` - Extract multiple fields as tuple

### Example 4: Get last child

```bash
org query '.children | reverse | .[0]' examples/ARCHIVE_small
```

**Query breakdown:**
1. `.children` - Access children field
2. `|` - Pipe to next filter
3. `reverse` - Reverse the list
4. `|` - Pipe to next filter
5. `.[0]` - Get first item (which is the last child)

### Example 5: Filter by level

```bash
org query '.[] | select(.level >= 2)' examples/ARCHIVE_small
```

**Query breakdown:**
1. `.[]` - Iterate over all nodes
2. `|` - Pipe to next filter
3. `select(.level >= 2)` - Keep only nodes with level >= 2

### Example 6: Find bugs

```bash
org query '.[] | select(.heading matches "bug")' examples/ARCHIVE_small
```

**Query breakdown:**
1. `.[]` - Iterate over all nodes
2. `|` - Pipe to next filter
3. `select(.heading matches "bug")` - Keep only nodes with "bug" in heading

## Open Questions

Before implementation begins, please clarify:

### 1. Variable Substitution

The example shows `.[$ offset : $limit]` - should we support:
- Variable substitution from command-line args?
- If yes, how should variables be specified? (e.g., `--var offset=5 --var limit=10`)
- Or should this be handled by the `--offset` and `--max-results` flags instead?

**Recommendation:** Start without variable substitution. Use `--offset` and `--max-results` flags for now. Add variable support in a future iteration if needed.

### 2. Property Access

OrgNode has a `get_property(name)` method for custom properties. Should we:
- Support `.properties.custom_name` syntax?
- Support `.get_property("custom_name")` function call syntax?
- Or defer this to a future extension?

**Recommendation:** Defer to future extension. Focus on direct field access first.

### 3. Error Recovery

Should the parser attempt error recovery or fail fast?
- Fail fast: Simpler, clearer errors
- Error recovery: More user-friendly but complex

**Recommendation:** Fail fast. Since the language might change frequently, prioritize clear errors over recovery.

### 4. Result Display

For nodes, should we:
- Always show full node representation (current behavior)?
- Add a flag like `--format=compact` for single-line output?
- Auto-detect based on query (e.g., field access shows just the field)?

**Recommendation:** Start with full node representation. Add formatting options in a future iteration based on user feedback.

### 5. Operator Precedence

What should be the operator precedence?
- Current plan: Pipe (lowest) → Tuple → Comparison → Function → Field access (highest)
- Is this intuitive for users?

**Recommendation:** Use the proposed precedence. It matches jq and similar tools.

## Future Considerations

### Potential Extensions

1. **Property Access**: Support `.properties.name` or `.get_property("name")`
2. **Variable Substitution**: Support `$var` in queries
3. **More Functions**: `map()`, `filter()`, `length`, `keys`, `values`
4. **More Operators**: `and`, `or`, `not`, `in`, `has`
5. **Type Coercion**: Automatic string-to-number conversion
6. **Null Safety**: Handle None values gracefully with `?.` operator
7. **Performance**: Optimize for large datasets with lazy evaluation
8. **Debugging**: Add `--explain` flag to show query execution plan
9. **Query Files**: Support `--query-file` for complex queries
10. **Output Formats**: JSON, CSV, table formats

### Maintenance Considerations

1. **Documentation**: Add query language reference to README
2. **Examples**: Create examples/ directory with common queries
3. **Error Messages**: Collect user feedback and improve error messages
4. **Performance**: Profile and optimize hot paths if needed
5. **Breaking Changes**: Version the query language syntax if major changes needed

## Timeline Estimate

| Phase | Estimated Time | Priority |
|-------|----------------|----------|
| AST Definitions | 1-2 hours | High |
| Parser Implementation | 3-4 hours | High |
| Executor Implementation | 3-4 hours | High |
| Exception Handling | 1 hour | High |
| Result Formatter | 1 hour | Medium |
| Integration | 2 hours | High |
| Testing | 2-3 hours | High |
| **Total** | **13-17 hours** | |

## Success Criteria

The implementation is complete when:

1. ✅ All query forms are parsed correctly
2. ✅ All functions are implemented and tested
3. ✅ All operators work with proper type checking
4. ✅ Error messages are clear and helpful
5. ✅ Example queries from this document work
6. ✅ Unit tests pass with ~70% coverage
7. ✅ Integration with `query` command is complete
8. ✅ Documentation is updated with examples
9. ✅ All validation checks pass (lint, type, format)

## Next Steps

1. Review this plan with the user
2. Address open questions
3. Begin implementation with Phase 1 (AST Definitions)
4. Iterate through phases sequentially
5. Test each phase before moving to the next
6. Update documentation as implementation progresses
