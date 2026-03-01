"""AST nodes for query language."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Expr:
    """Base AST expression type."""


@dataclass(frozen=True, slots=True)
class Identity(Expr):
    """Identity expression returning input stream unchanged."""


@dataclass(frozen=True, slots=True)
class Group(Expr):
    """Parenthesized expression."""

    expr: Expr


@dataclass(frozen=True, slots=True)
class FunctionCall(Expr):
    """Function invocation expression."""

    name: str
    argument: Expr | None


@dataclass(frozen=True, slots=True)
class Variable(Expr):
    """Variable lookup expression."""

    name: str


@dataclass(frozen=True, slots=True)
class NumberLiteral(Expr):
    """Numeric literal expression."""

    value: int | float


@dataclass(frozen=True, slots=True)
class StringLiteral(Expr):
    """String literal expression."""

    value: str


@dataclass(frozen=True, slots=True)
class BoolLiteral(Expr):
    """Boolean literal expression."""

    value: bool


@dataclass(frozen=True, slots=True)
class NoneLiteral(Expr):
    """None literal expression."""


@dataclass(frozen=True, slots=True)
class FieldAccess(Expr):
    """Attribute access expression."""

    base: Expr
    field: str


@dataclass(frozen=True, slots=True)
class BracketFieldAccess(Expr):
    """Bracket key access expression for mappings and objects."""

    base: Expr
    key_expr: Expr


@dataclass(frozen=True, slots=True)
class Iterate(Expr):
    """Collection iteration expression."""

    base: Expr


@dataclass(frozen=True, slots=True)
class Index(Expr):
    """Collection index expression."""

    base: Expr
    index_expr: Expr


@dataclass(frozen=True, slots=True)
class Slice(Expr):
    """Collection slice expression."""

    base: Expr
    start_expr: Expr | None
    end_expr: Expr | None


@dataclass(frozen=True, slots=True)
class BinaryOp(Expr):
    """Binary operation expression."""

    operator: str
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class TupleExpr(Expr):
    """Tuple expression combining multiple expressions."""

    items: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class Pipe(Expr):
    """Pipe expression sending left output into right input."""

    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class AsBinding(Expr):
    """Variable binding expression `<expr> as $name`."""

    source: Expr
    name: str


@dataclass(frozen=True, slots=True)
class LetBinding(Expr):
    """Scoped binding expression `let <value> as $name in <body>`."""

    value: Expr
    name: str
    body: Expr


@dataclass(frozen=True, slots=True)
class IfElse(Expr):
    """Conditional expression `if <condition> then <then> else <else>`."""

    condition: Expr
    then_expr: Expr
    else_expr: Expr


@dataclass(frozen=True, slots=True)
class Fold(Expr):
    """Fold subquery stream into a collection per input item."""

    expr: Expr | None
