"""Parser for query language expressions."""

from __future__ import annotations

import ast
from collections.abc import Callable

from parsy import ParseError, Parser, eof, forward_declaration, generate, regex, seq, string

from org.query_language.ast import (
    AsBinding,
    BinaryOp,
    BoolLiteral,
    BracketFieldAccess,
    Expr,
    FieldAccess,
    Fold,
    FunctionCall,
    Group,
    Identity,
    Index,
    Iterate,
    NoneLiteral,
    NumberLiteral,
    Pipe,
    Slice,
    StringLiteral,
    TupleExpr,
    Variable,
)
from org.query_language.errors import QueryParseError


KNOWN_FUNCTIONS = {
    "reverse",
    "unique",
    "select",
    "sort_by",
    "length",
    "sum",
    "join",
    "map",
}


def _decode_string(token_value: str) -> str:
    """Decode a double-quoted string literal token."""
    decoded = ast.literal_eval(token_value)
    if isinstance(decoded, str):
        return decoded
    raise QueryParseError("Invalid string literal")


def _keyword(name: str) -> Parser:
    """Build a keyword parser with identifier boundary."""
    return regex(rf"{name}(?![A-Za-z0-9_])")


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
    bare_identifier_value = identifier.map(StringLiteral)
    return (
        true_literal,
        false_literal,
        none_literal,
        variable,
        number_literal,
        string_literal,
        bare_identifier_value,
    )


def _build_function_call_parser(identifier: Parser, expr: Parser) -> Parser:
    """Build parser for function calls and bare identifier values."""

    @generate
    def function_call() -> object:
        name = yield identifier
        if name not in KNOWN_FUNCTIONS:
            return StringLiteral(name)
        arg = yield (_symbol("(") >> expr << _symbol(")")).optional()
        return FunctionCall(name, arg)

    return function_call


def _build_bracket_postfix_parser(index_expr: Parser) -> Parser:
    """Build parser for bracket-based postfix operators."""

    @generate
    def bracket_postfix() -> object:
        yield _symbol("[")
        empty = yield _symbol("]").optional()
        if empty is not None:
            return ("iterate",)

        start = yield index_expr.optional()
        colon = yield _symbol(":").optional()
        if colon is not None:
            end = yield index_expr.optional()
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
    def dot_expression() -> object:
        yield string(".")
        first_field = yield identifier.optional()
        if first_field is None:
            first_bracket = yield bracket_postfix.optional()
            current = (
                Identity() if first_bracket is None else _apply_postfix(Identity(), first_bracket)
            )
        else:
            current = FieldAccess(Identity(), first_field)

        rest = yield postfix.many()
        for op in rest:
            current = _apply_postfix(current, op)
        yield regex(r"\s*")
        return current

    return dot_expression


def _build_grouped_parser(expr: Parser) -> Parser:
    """Build parser for grouped expressions."""

    @generate
    def grouped() -> object:
        yield _symbol("(")
        inner = yield expr
        yield _symbol(")")
        return Group(inner)

    return grouped


def _build_fold_parser(expr: Parser) -> Parser:
    """Build parser for stream fold expressions `[subquery]`."""

    @generate
    def fold() -> object:
        yield _symbol("[")
        close = yield _symbol("]").optional()
        if close is not None:
            return Fold(None)
        inner = yield expr
        yield _symbol("]")
        return Fold(inner)

    return fold


def _build_postfix_chain_parser(
    base_parser: Parser,
    identifier: Parser,
    bracket_postfix: Parser,
) -> Parser:
    """Build parser applying postfix operators to any primary expression."""
    dot_field_postfix = (_symbol(".") >> identifier).map(_field_postfix)
    postfix = dot_field_postfix | bracket_postfix

    @generate
    def with_postfix() -> object:
        current = yield base_parser
        rest = yield postfix.many()
        for op in rest:
            current = _apply_postfix(current, op)
        return current

    return with_postfix


def _field_postfix(name: str) -> tuple[str, str]:
    """Create field postfix marker tuple."""
    return ("field", name)


def _binary_builder(operator: str, left: Expr, right: Expr) -> Expr:
    """Construct binary operation expression."""
    return BinaryOp(operator, left, right)


def _pipe_builder(_operator: str, left: Expr, right: Expr) -> Expr:
    """Construct pipe expression."""
    return Pipe(left, right)


def _make_parser() -> Parser:
    """Create the full expression parser."""
    ws = regex(r"\s*")
    identifier = _lexeme(regex(r"[A-Za-z_][A-Za-z0-9_]*"))
    number_token = _lexeme(regex(r"-?\d+(?:\.\d+)?"))
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
        bare_identifier_value,
    ) = _build_value_parser(identifier, number_token, string_token)
    function_call = _build_function_call_parser(identifier, expr)
    bracket_postfix = _build_bracket_postfix_parser(index_expr)
    dot_expression = _build_dot_expression_parser(identifier, bracket_postfix)
    grouped = _build_grouped_parser(expr)
    fold = _build_fold_parser(expr)

    base_atom = (
        dot_expression
        | grouped
        | fold
        | function_call
        | variable
        | true_literal
        | false_literal
        | none_literal
        | number_literal
        | string_literal
        | bare_identifier_value
    )
    atom = _build_postfix_chain_parser(base_atom, identifier, bracket_postfix)

    power = _chain_right(atom, _symbol("**"), _binary_builder)
    mult_op = _lexeme(
        string("*") | string("/") | _keyword("mod") | _keyword("rem") | _keyword("quot")
    )
    additive_op = _lexeme(string("+") | string("-"))
    multiply = _chain_left(power, mult_op, _binary_builder)
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

    as_binding = _build_as_binding_parser(comma, identifier)
    pipe = _chain_left(as_binding, _symbol("|"), _pipe_builder)

    expr.become(pipe)
    return ws >> expr << ws << eof


def _build_as_binding_parser(term: Parser, identifier: Parser) -> Parser:
    """Build parser for `<subquery> as $variable` binding."""

    @generate
    def parser() -> object:
        source = yield term
        bindings = yield (_lexeme(_keyword("as")) >> _symbol("$") >> identifier).many()
        current = source
        for name in bindings:
            current = AsBinding(current, name)
        return current

    return parser


def _apply_postfix(base: Expr, op: tuple[object, ...]) -> Expr:
    """Apply one postfix operator to an expression."""
    kind = op[0]
    if kind == "field":
        field = op[1]
        if not isinstance(field, str):
            raise QueryParseError("Invalid field name")
        return FieldAccess(base, field)
    if kind == "iterate":
        return Iterate(base)
    if kind == "slice":
        start_expr = op[1]
        end_expr = op[2]
        if start_expr is not None and not isinstance(start_expr, Expr):
            raise QueryParseError("Invalid slice start")
        if end_expr is not None and not isinstance(end_expr, Expr):
            raise QueryParseError("Invalid slice end")
        return Slice(base, start_expr, end_expr)
    if kind == "index":
        index_expr = op[1]
        if not isinstance(index_expr, Expr):
            raise QueryParseError("Invalid index expression")
        return Index(base, index_expr)
    if kind == "bracket-field":
        key_expr = op[1]
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
    def parser() -> object:
        left = yield term
        rest = yield seq(op, term).many()
        current = left
        for operator, right in rest:
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
    def parser() -> object:
        left = yield term
        rest = yield seq(op, term).many()
        if not rest:
            return left
        operators = [item[0] for item in rest]
        terms = [left, *[item[1] for item in rest]]
        current = terms[-1]
        for index in range(len(operators) - 1, -1, -1):
            current = builder(operators[index], terms[index], current)
        return current

    return parser


def _chain_comma(term: Parser) -> Parser:
    """Build comma-level tuple parser."""

    @generate
    def parser() -> object:
        first = yield term
        rest = yield (_symbol(",") >> term).many()
        if not rest:
            return first
        return TupleExpr((first, *rest))

    return parser


QUERY_PARSER = _make_parser()


def parse_query(query: str) -> Expr:
    """Parse query text into an AST expression."""
    try:
        result = QUERY_PARSER.parse(query)
    except ParseError as exc:
        raise QueryParseError(f"Invalid query syntax: {exc}") from exc
    if isinstance(result, Expr):
        return result
    raise QueryParseError("Parser did not produce an expression")
