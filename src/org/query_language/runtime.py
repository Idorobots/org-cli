"""Runtime evaluation for query language expressions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import product
from typing import cast

from org.query_language.ast import (
    BinaryOp,
    BoolLiteral,
    BracketFieldAccess,
    Expr,
    FieldAccess,
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


type Stream = list[object]


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
        result = list(stream)
    elif isinstance(expr, Group):
        result = evaluate_expr(expr.expr, stream, context)
    elif isinstance(expr, FunctionCall):
        result = _evaluate_function(expr, stream, context)
    elif isinstance(expr, Variable):
        result = [context.variables.get(expr.name)]
    elif isinstance(expr, NumberLiteral | StringLiteral | BoolLiteral):
        result = [expr.value]
    elif isinstance(expr, NoneLiteral):
        result = [None]
    return result


def _evaluate_operator_expr(expr: Expr, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate operator-based expressions."""
    if isinstance(expr, FieldAccess):
        base = evaluate_expr(expr.base, stream, context)
        return [_resolve_field(value, expr.field) for value in base]
    if isinstance(expr, BracketFieldAccess):
        return _evaluate_bracket_field_access(expr, stream, context)
    if isinstance(expr, Iterate):
        base = evaluate_expr(expr.base, stream, context)
        return _evaluate_iterate(base)
    if isinstance(expr, Index):
        return _evaluate_index(expr, stream, context)
    if isinstance(expr, Slice):
        return _evaluate_slice(expr, stream, context)
    if isinstance(expr, BinaryOp):
        return _evaluate_binary_op(expr, stream, context)
    raise QueryRuntimeError("Unsupported expression type")


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
    results: Stream = []
    for item in stream:
        base_values = evaluate_expr(expr.base, [item], context)
        key_values = evaluate_expr(expr.key_expr, [item], context)
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
    output: Stream = []
    for value in base:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            output.extend(list(value))
            continue
        raise QueryRuntimeError("Iteration requires a collection")
    return output


def _evaluate_index(expr: Index, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate index access with out-of-bounds returning None."""
    output: Stream = []
    for item in stream:
        base_values = evaluate_expr(expr.base, [item], context)
        index_values = evaluate_expr(expr.index_expr, [item], context)
        index_pairs = _broadcast(index_values, base_values)
        for index_value, base_value in index_pairs:
            output.append(_index_one(base_value, index_value))
    return output


def _index_one(base_value: object, index_value: object) -> object:
    """Apply one index operation."""
    if not isinstance(index_value, int):
        raise QueryRuntimeError("Index expression must evaluate to an integer")
    if isinstance(base_value, (list, tuple, str)):
        if -len(base_value) <= index_value < len(base_value):
            return base_value[index_value]
        return None
    raise QueryRuntimeError("Index access requires a list, tuple, or string")


def _evaluate_slice(expr: Slice, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate slice access with out-of-bounds returning empty lists."""
    output: Stream = []
    for item in stream:
        base_values = evaluate_expr(expr.base, [item], context)
        start_values: Stream
        end_values: Stream
        if expr.start_expr is None:
            start_values = [cast(object, None)]
        else:
            start_values = evaluate_expr(expr.start_expr, [item], context)
        if expr.end_expr is None:
            end_values = [cast(object, None)]
        else:
            end_values = evaluate_expr(expr.end_expr, [item], context)
        base_start_pairs = _broadcast(start_values, base_values)
        for start_value, base_value in base_start_pairs:
            end_pairs = _broadcast(end_values, [base_value])
            for end_value, base_value_for_end in end_pairs:
                output.append(_slice_one(base_value_for_end, start_value, end_value))
    return output


def _slice_one(base_value: object, start_value: object, end_value: object) -> object:
    """Apply one slice operation."""
    if start_value is not None and not isinstance(start_value, int):
        raise QueryRuntimeError("Slice start must be an integer or none")
    if end_value is not None and not isinstance(end_value, int):
        raise QueryRuntimeError("Slice end must be an integer or none")
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
    return [_apply_binary_operator(expr.operator, left, right) for left, right in pairs]


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
    raise QueryRuntimeError(f"Unsupported operator: {operator}")


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
    output: Stream = []
    for item in stream:
        parts = [evaluate_expr(item_expr, [item], context) for item_expr in expr.items]
        if any(len(part) == 0 for part in parts):
            continue
        for combo in product(*parts):
            output.append(tuple(combo))
    return output


def _evaluate_function(expr: FunctionCall, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate built-in function call expression."""
    if expr.name == "reverse":
        if expr.argument is not None:
            raise QueryRuntimeError("reverse does not accept an argument")
        return _func_reverse(stream)
    if expr.name == "unique":
        if expr.argument is not None:
            raise QueryRuntimeError("unique does not accept an argument")
        return _func_unique(stream)
    if expr.name == "length":
        if expr.argument is not None:
            raise QueryRuntimeError("length does not accept an argument")
        return _func_length(stream)
    if expr.name == "select":
        if expr.argument is None:
            raise QueryRuntimeError("select requires an argument")
        return _func_select(stream, expr.argument, context)
    if expr.name == "sort_by":
        if expr.argument is None:
            raise QueryRuntimeError("sort_by requires an argument")
        return _func_sort_by(stream, expr.argument, context)
    raise QueryRuntimeError(f"Unsupported function: {expr.name}")


def _func_reverse(stream: Stream) -> Stream:
    """Reverse stream or first collection element."""
    if len(stream) == 1 and isinstance(stream[0], (list, tuple)):
        collection = cast(list[object] | tuple[object, ...], stream[0])
        return [list(reversed(collection))]
    reversed_stream = list(stream)
    reversed_stream.reverse()
    return reversed_stream


def _func_unique(stream: Stream) -> Stream:
    """Return unique stream values preserving order."""
    seen: set[str] = set()
    output: Stream = []
    for value in stream:
        marker = repr(value)
        if marker in seen:
            continue
        seen.add(marker)
        output.append(value)
    return output


def _func_length(stream: Stream) -> Stream:
    """Return length for each stream value."""
    output: Stream = []
    for value in stream:
        if isinstance(value, (list, tuple, dict, set, str)):
            output.append(len(value))
            continue
        output.append(None)
    return output


def _func_select(stream: Stream, condition: Expr, context: EvalContext) -> Stream:
    """Filter stream by condition subquery truthiness."""
    output: Stream = []
    for item in stream:
        condition_values = evaluate_expr(condition, [item], context)
        if any(bool(value) for value in condition_values):
            output.append(item)
    return output


def _func_sort_by(stream: Stream, key_expr: Expr, context: EvalContext) -> Stream:
    """Sort stream by key expression evaluated per item in descending order."""
    decorated: list[tuple[int, object, object]] = []
    for index, item in enumerate(stream):
        key_values = evaluate_expr(key_expr, [item], context)
        key = key_values[0] if key_values else None
        decorated.append((index, key, item))

    def sort_key(value: tuple[int, object, object]) -> tuple[bool, str, int]:
        original_index, key, _item = value
        comparable = "" if key is None else str(key)
        return (key is None, comparable, original_index)

    ordered = sorted(decorated, key=sort_key, reverse=True)
    return [item for _idx, _key, item in ordered]


def _broadcast(left: Stream, right: Stream) -> list[tuple[object, object]]:
    """Broadcast two streams to compatible pairs."""
    if len(left) == len(right):
        return list(zip(left, right, strict=True))
    if len(left) == 1:
        return [(left[0], value) for value in right]
    if len(right) == 1:
        return [(value, right[0]) for value in left]
    raise QueryRuntimeError("Cannot combine streams with incompatible lengths")
