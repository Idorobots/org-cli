"""Parser for query language expressions."""

from __future__ import annotations

import ast
from collections.abc import Callable, Generator
from typing import Literal, cast

from parsy import ParseError, Parser, eof, forward_declaration, generate, regex, seq, string

from org.query_language.ast import (
    AsBinding,
    BinaryOp,
    BoolLiteral,
    BracketFieldAccess,
    DictAssignment,
    Expr,
    FieldAccess,
    Fold,
    FunctionCall,
    Group,
    Identity,
    IfElse,
    Index,
    Iterate,
    LetBinding,
    NoneLiteral,
    NumberLiteral,
    Pipe,
    Sequence,
    Slice,
    StringLiteral,
    TupleExpr,
    Variable,
)
from org.query_language.errors import QueryParseError


KNOWN_FUNCTIONS = {
    "bool",
    "float",
    "int",
    "reverse",
    "unique",
    "select",
    "sort_by",
    "length",
    "sum",
    "max",
    "min",
    "join",
    "map",
    "match",
    "sha256",
    "str",
    "ts",
    "type",
    "timestamp",
    "clock",
    "repeated_task",
    "uuid",
    "not",
    "debug",
}

type FieldPostfix = tuple[Literal["field"], str]
type IteratePostfix = tuple[Literal["iterate"]]
type SlicePostfix = tuple[Literal["slice"], Expr | None, Expr | None]
type IndexPostfix = tuple[Literal["index"], Expr]
type BracketFieldPostfix = tuple[Literal["bracket-field"], StringLiteral]
type PostfixOp = FieldPostfix | IteratePostfix | SlicePostfix | IndexPostfix | BracketFieldPostfix


def _parse_line_and_column(line_info: str) -> tuple[int, int]:
    """Parse line and column from parsy line info string."""
    line_text, sep, column_text = line_info.partition(":")
    if sep == "":
        return (0, 0)
    if not line_text.isdigit() or not column_text.isdigit():
        return (0, 0)
    return (int(line_text), int(column_text))


def _format_parse_error(query: str, exc: ParseError) -> str:
    """Build rich parse error message with query pointer."""
    line_number, column_number = _parse_line_and_column(exc.line_info())
    query_lines = query.splitlines()
    if not query_lines:
        query_lines = [query]

    error_line = query_lines[line_number] if 0 <= line_number < len(query_lines) else query
    pointer = " " * max(column_number, 0) + "^"
    return f"Invalid query syntax: {exc}\n\n{error_line}\n{pointer}"


def _decode_string(token_value: str) -> str:
    """Decode a double-quoted string literal token."""
    decoded = ast.literal_eval(token_value)
    if isinstance(decoded, str):
        return decoded
    raise QueryParseError("Invalid string literal")


def _keyword(name: str) -> Parser:
    """Build a keyword parser with identifier boundary."""
    return regex(rf"{name}(?![A-Za-z0-9_])").desc(name)


def _lexeme(parser: Parser) -> Parser:
    """Consume optional whitespace after parser."""
    ws = regex(r"\s*")
    return parser << ws


def _symbol(value: str) -> Parser:
    """Build a symbol token parser."""
    return _lexeme(string(value))


def _build_value_parser(
    identifier: Parser,
    number_token: Parser,
    string_token: Parser,
) -> tuple[
    Parser,
    Parser,
    Parser,
    Parser,
    Parser,
    Parser,
]:
    """Build parsers for literal and variable values."""
    true_literal = _lexeme(_keyword("true")).result(BoolLiteral(True))
    false_literal = _lexeme(_keyword("false")).result(BoolLiteral(False))
    none_literal = _lexeme(_keyword("none")).result(NoneLiteral())
    variable = (_symbol("$") >> identifier).map(Variable)
    number_literal = number_token.map(
        lambda v: NumberLiteral(float(v)) if "." in v else NumberLiteral(int(v))
    )
    string_literal = string_token.map(lambda v: StringLiteral(_decode_string(v)))
    return (
        true_literal,
        false_literal,
        none_literal,
        variable,
        number_literal,
        string_literal,
    )


def _build_function_call_parser(identifier: Parser, expr: Parser) -> Parser:
    """Build parser for known function calls."""

    @generate
    def function_call() -> Generator[Parser, object, FunctionCall]:
        name_result = yield identifier
        if not isinstance(name_result, str):
            raise QueryParseError("Invalid function name")
        name = name_result
        if name not in KNOWN_FUNCTIONS:
            available = ", ".join(sorted(KNOWN_FUNCTIONS))
            raise QueryParseError(f"Unknown function: {name}. Available functions: {available}")
        arg_result = yield (_symbol("(") >> expr << _symbol(")")).optional()
        if arg_result is not None and not isinstance(arg_result, Expr):
            raise QueryParseError("Invalid function argument")
        return FunctionCall(name, arg_result)

    return function_call


def _build_bracket_postfix_parser(index_expr: Parser) -> Parser:
    """Build parser for bracket-based postfix operators."""

    @generate
    def bracket_postfix() -> Generator[Parser, object, PostfixOp]:
        yield _symbol("[")
        empty = yield _symbol("]").optional()
        if empty is not None:
            return ("iterate",)

        start_result = yield index_expr.optional()
        if start_result is not None and not isinstance(start_result, Expr):
            raise QueryParseError("Invalid bracket expression")
        start = start_result
        colon = yield _symbol(":").optional()
        if colon is not None:
            end_result = yield index_expr.optional()
            if end_result is not None and not isinstance(end_result, Expr):
                raise QueryParseError("Invalid slice expression")
            end = end_result
            yield _symbol("]")
            return ("slice", start, end)

        yield _symbol("]")
        if start is None:
            raise QueryParseError("Expected index, key, or slice in brackets")
        if isinstance(start, StringLiteral):
            return ("bracket-field", start)
        return ("index", start)

    return bracket_postfix


def _build_dot_expression_parser(identifier: Parser, bracket_postfix: Parser) -> Parser:
    """Build parser for dot-rooted path expressions."""
    dot_field_postfix = (_symbol(".") >> identifier).map(_field_postfix)
    postfix = dot_field_postfix | bracket_postfix

    @generate
    def dot_expression() -> Generator[Parser, object, Expr]:
        yield string(".")
        first_field_result = yield identifier.optional()
        if first_field_result is not None and not isinstance(first_field_result, str):
            raise QueryParseError("Invalid field name")
        first_field = first_field_result

        current: Expr
        if first_field is None:
            first_bracket_result = yield bracket_postfix.optional()
            if first_bracket_result is not None and not isinstance(first_bracket_result, tuple):
                raise QueryParseError("Invalid bracket postfix")
            first_bracket = cast(PostfixOp | None, first_bracket_result)
            current = (
                Identity() if first_bracket is None else _apply_postfix(Identity(), first_bracket)
            )
        else:
            current = FieldAccess(Identity(), first_field)

        rest_result = yield postfix.many()
        if not isinstance(rest_result, list):
            raise QueryParseError("Invalid postfix chain")
        rest = cast(list[PostfixOp], rest_result)
        for op in rest:
            current = _apply_postfix(current, op)
        yield regex(r"\s*")
        return current

    return dot_expression


def _build_grouped_parser(expr: Parser) -> Parser:
    """Build parser for grouped expressions."""

    @generate
    def grouped() -> Generator[Parser, object, Group]:
        yield _symbol("(")
        inner = yield expr
        if not isinstance(inner, Expr):
            raise QueryParseError("Invalid grouped expression")
        yield _symbol(")")
        return Group(inner)

    return grouped


def _build_fold_parser(expr: Parser) -> Parser:
    """Build parser for stream fold expressions `[subquery]`."""

    @generate
    def fold() -> Generator[Parser, object, Fold]:
        yield _symbol("[")
        close = yield _symbol("]").optional()
        if close is not None:
            return Fold(None)
        inner = yield expr
        if not isinstance(inner, Expr):
            raise QueryParseError("Invalid fold expression")
        yield _symbol("]")
        return Fold(inner)

    return fold


def _build_let_binding_parser(value_expr: Parser, body_expr: Parser, identifier: Parser) -> Parser:
    """Build parser for scoped let binding expressions."""

    @generate
    def let_binding() -> Generator[Parser, object, LetBinding]:
        yield _lexeme(_keyword("let"))
        value_result = yield value_expr
        if not isinstance(value_result, Expr):
            raise QueryParseError("Invalid let value expression")
        yield _lexeme(_keyword("as"))
        yield _symbol("$")
        name_result = yield identifier
        if not isinstance(name_result, str):
            raise QueryParseError("Invalid let variable name")
        body_result = yield (_lexeme(_keyword("in")) >> body_expr)
        if not isinstance(body_result, Expr):
            raise QueryParseError("Invalid let body expression")
        return LetBinding(value_result, name_result, body_result)

    return let_binding


def _build_if_else_parser(expr: Parser) -> Parser:
    """Build parser for conditional if-then-elif-else expressions."""

    elif_clause = seq(
        _lexeme(_keyword("elif")) >> (expr << _lexeme(_keyword("then"))),
        expr,
    )

    @generate
    def if_else() -> Generator[Parser, object, IfElse]:
        yield _lexeme(_keyword("if"))
        condition_result = yield (expr << _lexeme(_keyword("then")))
        if not isinstance(condition_result, Expr):
            raise QueryParseError("Invalid if condition expression")
        then_result = yield expr
        if not isinstance(then_result, Expr):
            raise QueryParseError("Invalid then expression")

        elif_clauses_result = yield elif_clause.many()
        if not isinstance(elif_clauses_result, list):
            raise QueryParseError("Invalid elif clauses")
        elif_clauses = cast(list[tuple[object, object]], elif_clauses_result)

        yield _lexeme(_keyword("else"))
        else_result = yield expr
        if not isinstance(else_result, Expr):
            raise QueryParseError("Invalid else expression")

        branches: list[tuple[Expr, Expr]] = [(condition_result, then_result)]
        for elif_condition, elif_then in elif_clauses:
            if not isinstance(elif_condition, Expr):
                raise QueryParseError("Invalid elif condition expression")
            if not isinstance(elif_then, Expr):
                raise QueryParseError("Invalid elif then expression")
            branches.append((elif_condition, elif_then))

        current_else: Expr = else_result
        for branch_condition, branch_then in reversed(branches):
            current_else = IfElse(branch_condition, branch_then, current_else)
        return cast(IfElse, current_else)

    return if_else


def _build_postfix_chain_parser(
    base_parser: Parser,
    identifier: Parser,
    bracket_postfix: Parser,
) -> Parser:
    """Build parser applying postfix operators to any primary expression."""
    dot_field_postfix = (_symbol(".") >> identifier).map(_field_postfix)
    postfix = dot_field_postfix | bracket_postfix

    @generate
    def with_postfix() -> Generator[Parser, object, Expr]:
        current_result = yield base_parser
        if not isinstance(current_result, Expr):
            raise QueryParseError("Invalid base expression")
        current: Expr = current_result

        rest_result = yield postfix.many()
        if not isinstance(rest_result, list):
            raise QueryParseError("Invalid postfix chain")
        rest = cast(list[PostfixOp], rest_result)
        for op in rest:
            current = _apply_postfix(current, op)
        return current

    return with_postfix


def _field_postfix(name: str) -> FieldPostfix:
    """Create field postfix marker tuple."""
    return ("field", name)


def _binary_builder(operator: str, left: Expr, right: Expr) -> Expr:
    """Construct binary operation expression."""
    return BinaryOp(operator, left, right)


def _pipe_builder(_operator: str, left: Expr, right: Expr) -> Expr:
    """Construct pipe expression."""
    return Pipe(left, right)


def _sequence_builder(_operator: str, left: Expr, right: Expr) -> Expr:
    """Construct sequencing expression."""
    return Sequence(left, right)


def _assignment_builder(_operator: str, left: Expr, right: Expr) -> Expr:
    """Construct dictionary assignment expression."""
    return _build_assignment_expr(left, right)


def _build_assignment_expr(left: Expr, right: Expr) -> Expr:
    """Build assignment expression from supported assignment targets."""
    if isinstance(left, FieldAccess):
        return DictAssignment(left.base, StringLiteral(left.field), right)
    if isinstance(left, Index):
        return DictAssignment(left.base, left.index_expr, right)
    if isinstance(left, BracketFieldAccess):
        return DictAssignment(left.base, left.key_expr, right)
    raise QueryParseError("Assignment target must be .field or [<field-subquery>] access")


def _make_parser() -> Parser:
    """Create the full expression parser."""
    ws = regex(r"\s*")
    identifier = _lexeme(regex(r"[A-Za-z_][A-Za-z0-9_]*"))
    number_token = _lexeme(regex(r"\d+(?:\.\d+)?"))
    string_token = _lexeme(regex(r'"(?:[^"\\]|\\.)*"'))

    expr = forward_declaration()
    index_expr = forward_declaration()

    (
        true_literal,
        false_literal,
        none_literal,
        variable,
        number_literal,
        string_literal,
    ) = _build_value_parser(identifier, number_token, string_token)
    function_call = _build_function_call_parser(identifier, expr)
    bracket_postfix = _build_bracket_postfix_parser(index_expr)
    dot_expression = _build_dot_expression_parser(identifier, bracket_postfix)
    grouped = _build_grouped_parser(expr)
    fold = _build_fold_parser(expr)
    if_else = _build_if_else_parser(expr)

    base_atom = (
        dot_expression
        | grouped
        | fold
        | if_else
        | true_literal
        | false_literal
        | none_literal
        | function_call
        | variable
        | number_literal
        | string_literal
    )
    atom = _build_postfix_chain_parser(base_atom, identifier, bracket_postfix)

    power = _chain_right(atom, _symbol("**"), _binary_builder)

    @generate
    def unary() -> Generator[Parser, object, Expr]:
        minuses_result = yield _symbol("-").many()
        if not isinstance(minuses_result, list):
            raise QueryParseError("Invalid unary minus expression")
        value_result = yield power
        if not isinstance(value_result, Expr):
            raise QueryParseError("Invalid unary minus operand")

        current: Expr = value_result
        for _minus in minuses_result:
            current = BinaryOp("-", NumberLiteral(0), current)
        return current

    mult_op = _lexeme(
        string("*") | string("/") | _keyword("mod") | _keyword("rem") | _keyword("quot")
    )
    additive_op = _lexeme(string("+") | string("-"))
    multiply = _chain_left(unary, mult_op, _binary_builder)
    additive = _chain_left(multiply, additive_op, _binary_builder)
    index_expr.become(additive)

    compare_op = _lexeme(
        string(">=")
        | string("<=")
        | string("==")
        | string("!=")
        | string(">")
        | string("<")
        | _keyword("matches")
        | _keyword("in")
    )
    bool_op = _lexeme(_keyword("and") | _keyword("or"))

    comparison = _chain_left(additive, compare_op, _binary_builder)
    boolean = _chain_left(comparison, bool_op, _binary_builder)
    comma = _chain_comma(boolean)

    let_binding = _build_let_binding_parser(comma, expr, identifier)
    as_binding = _build_as_binding_parser(let_binding | comma, identifier)
    assignment = _chain_right(as_binding, _symbol("="), _assignment_builder)
    sequence = _chain_left(assignment, _symbol(";"), _sequence_builder)
    pipe = _chain_left(sequence, _symbol("|"), _pipe_builder)

    expr.become(pipe)
    return ws >> expr << ws << eof


def _build_as_binding_parser(term: Parser, identifier: Parser) -> Parser:
    """Build parser for `<subquery> as $variable` binding."""

    @generate
    def parser() -> Generator[Parser, object, Expr]:
        source_result = yield term
        if not isinstance(source_result, Expr):
            raise QueryParseError("Invalid binding source")
        bindings_result = yield (_lexeme(_keyword("as")) >> _symbol("$") >> identifier).many()
        if not isinstance(bindings_result, list):
            raise QueryParseError("Invalid binding list")
        bindings = cast(list[str], bindings_result)

        current: Expr = source_result
        for name in bindings:
            current = AsBinding(current, name)
        return current

    return parser


def _apply_postfix(base: Expr, op: PostfixOp) -> Expr:
    """Apply one postfix operator to an expression."""
    match op:
        case ("field", field):
            if not isinstance(field, str):
                raise QueryParseError("Invalid field name")
            return FieldAccess(base, field)
        case ("iterate",):
            return Iterate(base)
        case ("slice", start_expr, end_expr):
            if start_expr is not None and not isinstance(start_expr, Expr):
                raise QueryParseError("Invalid slice start")
            if end_expr is not None and not isinstance(end_expr, Expr):
                raise QueryParseError("Invalid slice end")
            return Slice(base, start_expr, end_expr)
        case ("index", index_expr):
            if not isinstance(index_expr, Expr):
                raise QueryParseError("Invalid index expression")
            return Index(base, index_expr)
        case ("bracket-field", key_expr):
            if not isinstance(key_expr, Expr):
                raise QueryParseError("Invalid bracket field expression")
            return BracketFieldAccess(base, key_expr)

    raise QueryParseError("Unknown postfix operator")


def _chain_left(
    term: Parser,
    op: Parser,
    builder: Callable[[str, Expr, Expr], Expr],
) -> Parser:
    """Build a left-associative parser from term and operator parsers."""

    @generate
    def parser() -> Generator[Parser, object, Expr]:
        left_result = yield term
        if not isinstance(left_result, Expr):
            raise QueryParseError("Invalid left expression")

        rest_result = yield seq(op, term).many()
        if not isinstance(rest_result, list):
            raise QueryParseError("Invalid operator chain")

        current: Expr = left_result
        rest = cast(list[tuple[object, object]], rest_result)
        for operator, right in rest:
            if not isinstance(operator, str):
                raise QueryParseError("Invalid operator")
            if not isinstance(right, Expr):
                raise QueryParseError("Invalid right expression")
            current = builder(operator, current, right)
        return current

    return parser


def _chain_right(
    term: Parser,
    op: Parser,
    builder: Callable[[str, Expr, Expr], Expr],
) -> Parser:
    """Build a right-associative parser from term and operator parsers."""

    @generate
    def parser() -> Generator[Parser, object, Expr]:
        left_result = yield term
        if not isinstance(left_result, Expr):
            raise QueryParseError("Invalid left expression")

        rest_result = yield seq(op, term).many()
        if not isinstance(rest_result, list):
            raise QueryParseError("Invalid operator chain")
        rest = cast(list[tuple[object, object]], rest_result)

        if not rest:
            return left_result

        operators: list[str] = []
        terms: list[Expr] = [left_result]
        for operator, right in rest:
            if not isinstance(operator, str):
                raise QueryParseError("Invalid operator")
            if not isinstance(right, Expr):
                raise QueryParseError("Invalid right expression")
            operators.append(operator)
            terms.append(right)

        current: Expr = terms[-1]
        for index in range(len(operators) - 1, -1, -1):
            current = builder(operators[index], terms[index], current)
        return current

    return parser


def _chain_comma(term: Parser) -> Parser:
    """Build comma-level tuple parser."""

    @generate
    def parser() -> Generator[Parser, object, Expr]:
        first_result = yield term
        if not isinstance(first_result, Expr):
            raise QueryParseError("Invalid tuple expression")
        rest_result = yield (_symbol(",") >> term).many()
        if not isinstance(rest_result, list):
            raise QueryParseError("Invalid tuple expression")
        rest = cast(list[Expr], rest_result)
        if not rest:
            return first_result
        return TupleExpr((first_result, *rest))

    return parser


QUERY_PARSER = _make_parser()


def parse_query(query: str) -> Expr:
    """Parse query text into an AST expression."""
    try:
        result = QUERY_PARSER.parse(query)
    except ParseError as exc:
        raise QueryParseError(_format_parse_error(query, exc)) from exc
    if isinstance(result, Expr):
        return result
    raise QueryParseError("Parser did not produce an expression")
