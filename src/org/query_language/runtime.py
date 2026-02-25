"""Runtime evaluation for query language expressions."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product
from math import trunc
from typing import cast

from orgparse.node import OrgRootNode

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
from org.query_language.errors import QueryRuntimeError


class Stream(list[object]):
    """Typed stream container for query evaluation values."""


def _stream(values: Iterable[object] = ()) -> Stream:
    """Build a stream from iterable values."""
    return Stream(values)


@dataclass(frozen=True, slots=True)
class EvalContext:
    """Execution context for runtime evaluation."""

    variables: dict[str, object]


def evaluate_expr(expr: Expr, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate an expression over the provided stream."""
    atomic_result = _evaluate_atomic(expr, stream, context)
    if atomic_result is not None:
        return atomic_result

    if isinstance(expr, Pipe):
        left = evaluate_expr(expr.left, stream, context)
        return evaluate_expr(expr.right, left, context)
    if isinstance(expr, TupleExpr):
        return _evaluate_tuple_expr(expr, stream, context)
    return _evaluate_operator_expr(expr, stream, context)


def _evaluate_atomic(expr: Expr, stream: Stream, context: EvalContext) -> Stream | None:
    """Evaluate expressions that do not require operator dispatch."""
    result: Stream | None = None
    if isinstance(expr, Identity):
        result = _stream(stream)
    elif isinstance(expr, Group):
        result = evaluate_expr(expr.expr, stream, context)
    elif isinstance(expr, FunctionCall):
        result = _evaluate_function(expr, stream, context)
    elif isinstance(expr, Variable):
        result = _stream([context.variables.get(expr.name)])
    elif isinstance(expr, NumberLiteral | StringLiteral | BoolLiteral):
        result = _stream([expr.value])
    elif isinstance(expr, NoneLiteral):
        result = _stream([None])
    elif isinstance(expr, AsBinding):
        result = _evaluate_as_binding(expr, stream, context)
    return result


def _evaluate_operator_expr(expr: Expr, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate operator-based expressions."""
    result: Stream | None = None
    if isinstance(expr, FieldAccess):
        base = evaluate_expr(expr.base, stream, context)
        result = _stream([_resolve_field(value, expr.field) for value in base])
    elif isinstance(expr, BracketFieldAccess):
        result = _evaluate_bracket_field_access(expr, stream, context)
    elif isinstance(expr, Iterate):
        base = evaluate_expr(expr.base, stream, context)
        result = _evaluate_iterate(base)
    elif isinstance(expr, Index):
        result = _evaluate_index(expr, stream, context)
    elif isinstance(expr, Slice):
        result = _evaluate_slice(expr, stream, context)
    elif isinstance(expr, BinaryOp):
        result = _evaluate_binary_op(expr, stream, context)
    elif isinstance(expr, Fold):
        result = _evaluate_fold(expr, stream, context)
    if result is not None:
        return result
    raise QueryRuntimeError("Unsupported expression type")


def _evaluate_as_binding(expr: AsBinding, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate variable binding and pass through bound values."""
    bound_values = evaluate_expr(expr.source, stream, context)
    bound_value = bound_values[0] if len(bound_values) == 1 else bound_values
    context.variables[expr.name] = bound_value
    return bound_values


def _evaluate_fold(expr: Fold, stream: Stream, context: EvalContext) -> Stream:
    """Fold subquery stream into one list per input stream item."""
    if expr.expr is None:
        return _stream([[] for _item in stream])

    output = _stream()
    for item in stream:
        folded_values = evaluate_expr(expr.expr, _stream([item]), context)
        folded: list[object] = []
        for value in folded_values:
            if isinstance(value, tuple):
                folded.extend(list(value))
                continue
            folded.append(value)
        output.append(folded)
    return output


def _resolve_field(value: object, field: str) -> object:
    """Resolve attribute-like field access with None fallback."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(field)

    sentinel = object()
    attr_value = getattr(value, field, sentinel)
    if attr_value is sentinel:
        return None
    return attr_value


def _evaluate_bracket_field_access(
    expr: BracketFieldAccess, stream: Stream, context: EvalContext
) -> Stream:
    """Evaluate bracket key access for each item in stream."""
    results = _stream()
    for item in stream:
        base_values = evaluate_expr(expr.base, _stream([item]), context)
        key_values = evaluate_expr(expr.key_expr, _stream([item]), context)
        for base in base_values:
            for key in key_values:
                results.append(_resolve_bracket_key(base, key))
    return results


def _resolve_bracket_key(base: object, key: object) -> object:
    """Resolve one bracket key lookup with None fallback for misses."""
    if base is None:
        return None
    if isinstance(key, str):
        if isinstance(base, dict):
            return base.get(key)
        return _resolve_field(base, key)
    if isinstance(key, int):
        if isinstance(base, (list, tuple, str)):
            if -len(base) <= key < len(base):
                return base[key]
            return None
        raise QueryRuntimeError("Index access requires a list, tuple, or string")
    raise QueryRuntimeError("Bracket key must be a string or integer")


def _evaluate_iterate(base: Stream) -> Stream:
    """Evaluate collection iteration and flatten one level."""
    output = _stream()
    for value in base:
        if value is None:
            continue
        if isinstance(value, OrgRootNode):
            output.extend(list(value[1:]))
            continue
        if isinstance(value, (list, tuple, set)):
            output.extend(list(value))
            continue
        raise QueryRuntimeError("Iteration requires a collection")
    return output


def _evaluate_index(expr: Index, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate index access with out-of-bounds returning None."""
    output = _stream()
    for item in stream:
        base_values = evaluate_expr(expr.base, _stream([item]), context)
        index_values = evaluate_expr(expr.index_expr, _stream([item]), context)
        index_pairs = _broadcast(index_values, base_values)
        for index_value, base_value in index_pairs:
            output.append(_index_one(base_value, index_value))
    return output


def _index_one(base_value: object, index_value: object) -> object:
    """Apply one index operation."""
    if not isinstance(index_value, int):
        raise QueryRuntimeError("Index expression must evaluate to an integer")
    if isinstance(base_value, OrgRootNode):
        nodes = list(base_value[1:])
        if -len(nodes) <= index_value < len(nodes):
            return nodes[index_value]
        return None
    if isinstance(base_value, (list, tuple, str)):
        if -len(base_value) <= index_value < len(base_value):
            return base_value[index_value]
        return None
    raise QueryRuntimeError("Index access requires a list, tuple, or string")


def _evaluate_slice(expr: Slice, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate slice access with out-of-bounds returning empty lists."""
    output = _stream()
    for item in stream:
        base_values = evaluate_expr(expr.base, _stream([item]), context)
        start_values: Stream
        end_values: Stream
        if expr.start_expr is None:
            start_values = _stream([cast(object, None)])
        else:
            start_values = evaluate_expr(expr.start_expr, _stream([item]), context)
        if expr.end_expr is None:
            end_values = _stream([cast(object, None)])
        else:
            end_values = evaluate_expr(expr.end_expr, _stream([item]), context)
        base_start_pairs = _broadcast(start_values, base_values)
        for start_value, base_value in base_start_pairs:
            end_pairs = _broadcast(end_values, _stream([base_value]))
            for end_value, base_value_for_end in end_pairs:
                output.append(_slice_one(base_value_for_end, start_value, end_value))
    return output


def _slice_one(base_value: object, start_value: object, end_value: object) -> object:
    """Apply one slice operation."""
    if start_value is not None and not isinstance(start_value, int):
        raise QueryRuntimeError("Slice start must be an integer or none")
    if end_value is not None and not isinstance(end_value, int):
        raise QueryRuntimeError("Slice end must be an integer or none")
    if isinstance(base_value, OrgRootNode):
        nodes = list(base_value[1:])
        return nodes[start_value:end_value]
    if isinstance(base_value, (list, tuple, str)):
        start_index = start_value
        end_index = end_value
        return base_value[start_index:end_index]
    raise QueryRuntimeError("Slice access requires a list, tuple, or string")


def _evaluate_binary_op(expr: BinaryOp, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate binary operations over stream values with broadcasting."""
    left_values = evaluate_expr(expr.left, stream, context)
    right_values = evaluate_expr(expr.right, stream, context)
    pairs = _broadcast(left_values, right_values)
    return _stream([_apply_binary_operator(expr.operator, left, right) for left, right in pairs])


def _apply_binary_operator(operator: str, left: object, right: object) -> object:
    """Apply one binary operator to two values."""
    if operator in {"==", "!="}:
        return _apply_equality(operator, left, right)
    if operator in {">", "<", ">=", "<="}:
        return _compare(operator, left, right)
    if operator == "matches":
        if not isinstance(left, str) or not isinstance(right, str):
            raise QueryRuntimeError("matches operator requires two strings")
        return bool(re.compile(right).match(left))
    if operator in {"and", "or"}:
        return _apply_boolean(operator, left, right)
    if operator == "in":
        return _apply_in_operator(left, right)
    if operator in {"**", "*", "/", "+", "-", "mod", "rem", "quot"}:
        return _apply_numeric_operator(operator, left, right)
    raise QueryRuntimeError(f"Unsupported operator: {operator}")


def _apply_numeric_operator(operator: str, left: object, right: object) -> object:
    """Apply numeric operators with arithmetic semantics."""
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        raise QueryRuntimeError(f"{operator} operator requires numeric operands")
    left_num = left
    right_num = right

    if operator in {"**", "*", "+", "-"}:
        return _apply_simple_numeric_operator(operator, left_num, right_num)

    if operator == "/":
        _guard_non_zero(right_num, "Division by zero")
        return left_num / right_num

    if operator == "mod":
        _guard_non_zero(right_num, "Modulo by zero")
        modulus = abs(right_num)
        return ((left_num % modulus) + modulus) % modulus

    if operator in {"quot", "rem"}:
        _guard_non_zero(right_num, f"{'Quotient' if operator == 'quot' else 'Remainder'} by zero")
        quotient = trunc(left_num / right_num)
        return quotient if operator == "quot" else left_num - (right_num * quotient)

    raise QueryRuntimeError(f"Unsupported numeric operator: {operator}")


def _apply_simple_numeric_operator(operator: str, left: int | float, right: int | float) -> object:
    """Apply non-dividing numeric operators."""
    operations: dict[str, object] = {
        "**": left**right,
        "*": left * right,
        "+": left + right,
        "-": left - right,
    }
    return operations[operator]


def _guard_non_zero(value: int | float, message: str) -> None:
    """Raise runtime error when value is zero."""
    if value == 0:
        raise QueryRuntimeError(message)


def _apply_in_operator(left: object, right: object) -> bool:
    """Apply membership operator."""
    if not isinstance(right, (list, tuple, set, dict, str)):
        raise QueryRuntimeError("in operator requires a collection on the right")
    if isinstance(right, str):
        if not isinstance(left, str):
            return False
        return left in right
    right_collection = cast(
        list[object] | tuple[object, ...] | set[object] | dict[object, object],
        right,
    )
    return left in right_collection


def _apply_equality(operator: str, left: object, right: object) -> bool:
    """Apply equality operators."""
    if operator == "==":
        return left == right
    return left != right


def _apply_boolean(operator: str, left: object, right: object) -> bool:
    """Apply boolean operators."""
    if not isinstance(left, bool) or not isinstance(right, bool):
        raise QueryRuntimeError(f"{operator} operator requires two booleans")
    if operator == "and":
        return left and right
    return left or right


def _compare(operator: str, left: object, right: object) -> bool:
    """Apply numeric or string comparison operators."""
    is_numeric = isinstance(left, (int, float)) and isinstance(right, (int, float))
    is_string = isinstance(left, str) and isinstance(right, str)
    if not is_numeric and not is_string:
        raise QueryRuntimeError("Comparison operators require numeric or string operands")
    if is_numeric:
        left_value_num = cast(float | int, left)
        right_value_num = cast(float | int, right)
        return _compare_numeric(operator, left_value_num, right_value_num)
    left_value_str = cast(str, left)
    right_value_str = cast(str, right)
    return _compare_string(operator, left_value_str, right_value_str)


def _compare_numeric(operator: str, left: float | int, right: float | int) -> bool:
    """Apply numeric comparisons."""
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    raise QueryRuntimeError(f"Unsupported comparison operator: {operator}")


def _compare_string(operator: str, left: str, right: str) -> bool:
    """Apply string comparisons."""
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    raise QueryRuntimeError(f"Unsupported comparison operator: {operator}")


def _evaluate_tuple_expr(expr: TupleExpr, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate comma-separated expressions into tuple values."""
    output = _stream()
    for item in stream:
        parts = [evaluate_expr(item_expr, _stream([item]), context) for item_expr in expr.items]
        if any(len(part) == 0 for part in parts):
            continue
        for combo in product(*parts):
            output.append(tuple(combo))
    return output


def _evaluate_function(expr: FunctionCall, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate built-in function call expression."""
    no_arg_functions = {
        "reverse": _func_reverse,
        "unique": _func_unique,
        "length": _func_length,
        "sum": _func_sum,
    }
    arg_functions = {
        "select": _func_select,
        "sort_by": _func_sort_by,
        "join": _func_join,
        "map": _func_map,
    }

    if expr.name in no_arg_functions:
        if expr.argument is not None:
            raise QueryRuntimeError(f"{expr.name} does not accept an argument")
        return no_arg_functions[expr.name](stream)

    if expr.name in arg_functions:
        if expr.argument is None:
            raise QueryRuntimeError(f"{expr.name} requires an argument")
        return arg_functions[expr.name](stream, expr.argument, context)

    raise QueryRuntimeError(f"Unsupported function: {expr.name}")


def _func_reverse(stream: Stream) -> Stream:
    """Reverse stream or first collection element."""
    if len(stream) == 1 and isinstance(stream[0], (list, tuple)):
        collection = cast(list[object] | tuple[object, ...], stream[0])
        return _stream([list(reversed(collection))])
    reversed_stream = _stream(stream)
    reversed_stream.reverse()
    return reversed_stream


def _func_unique(stream: Stream) -> Stream:
    """Return unique stream values preserving order."""
    seen: set[str] = set()
    output = _stream()
    for value in stream:
        marker = repr(value)
        if marker in seen:
            continue
        seen.add(marker)
        output.append(value)
    return output


def _func_length(stream: Stream) -> Stream:
    """Return length for each stream value."""
    output = _stream()
    for value in stream:
        if isinstance(value, OrgRootNode):
            output.append(len(list(value[1:])))
            continue
        if isinstance(value, (list, tuple, dict, set, str)):
            output.append(len(value))
            continue
        output.append(None)
    return output


def _func_sum(stream: Stream) -> Stream:
    """Return sum for each collection value in stream."""
    output = _stream()
    for value in stream:
        values = _extract_numeric_collection(value)
        output.append(sum(values))
    return output


def _func_select(stream: Stream, condition: Expr, context: EvalContext) -> Stream:
    """Filter stream by condition subquery truthiness."""
    output = _stream()
    for item in stream:
        condition_values = evaluate_expr(condition, _stream([item]), context)
        if any(bool(value) for value in condition_values):
            output.append(item)
    return output


def _func_sort_by(stream: Stream, key_expr: Expr, context: EvalContext) -> Stream:
    """Sort stream by key expression evaluated per item in descending order."""
    decorated: list[tuple[int, object, object]] = []
    for index, item in enumerate(stream):
        key_values = evaluate_expr(key_expr, _stream([item]), context)
        key = key_values[0] if key_values else None
        decorated.append((index, key, item))

    def sort_key(value: tuple[int, object, object]) -> tuple[bool, str, int]:
        original_index, key, _item = value
        comparable = "" if key is None else str(key)
        return (key is None, comparable, original_index)

    ordered = sorted(decorated, key=sort_key, reverse=True)
    return _stream([item for _idx, _key, item in ordered])


def _func_join(stream: Stream, separator_expr: Expr, context: EvalContext) -> Stream:
    """Join collection values into strings using dynamic separator expression."""
    output = _stream()
    for item in stream:
        separator_values = evaluate_expr(separator_expr, _stream([item]), context)
        separator = separator_values[0] if separator_values else ""
        if not isinstance(separator, str):
            raise QueryRuntimeError("join separator must evaluate to a string")
        collection = _extract_collection(item)
        output.append(separator.join(str(value) for value in collection))
    return output


def _func_map(stream: Stream, subquery: Expr, context: EvalContext) -> Stream:
    """Map each collection value using a subquery."""
    output = _stream()
    for item in stream:
        collection = _extract_collection(item)
        mapped: list[object] = []
        for value in collection:
            mapped.extend(evaluate_expr(subquery, _stream([value]), context))
        output.append(mapped)
    return output


def _extract_collection(value: object) -> list[object]:
    """Extract a value as a query collection list."""
    if isinstance(value, OrgRootNode):
        return list(value[1:])
    if isinstance(value, (list, tuple, set)):
        return list(value)
    raise QueryRuntimeError("Operation requires a collection")


def _extract_numeric_collection(value: object) -> list[int | float]:
    """Extract numeric collection values."""
    collection = _extract_collection(value)
    if not all(isinstance(item, (int, float)) for item in collection):
        raise QueryRuntimeError("sum requires a numeric collection")
    return cast(list[int | float], collection)


def _broadcast(left: Stream, right: Stream) -> list[tuple[object, object]]:
    """Broadcast two streams to compatible pairs."""
    if len(left) == len(right):
        return list(zip(left, right, strict=True))
    if len(left) == 1:
        return [(left[0], value) for value in right]
    if len(right) == 1:
        return [(value, right[0]) for value in left]
    raise QueryRuntimeError("Cannot combine streams with incompatible lengths")
