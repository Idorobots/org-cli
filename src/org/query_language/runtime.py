"""Runtime evaluation for query language expressions."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from itertools import product
from math import trunc
from typing import cast
from uuid import uuid4

from orgparse.date import OrgDate, OrgDateClock, OrgDateRepeatedTask
from orgparse.node import OrgRootNode

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
from org.query_language.errors import QueryRuntimeError


class Stream(list[object]):
    """Typed stream container for query evaluation values."""


_OPERATOR_NOT_HANDLED = object()
type ComparableKey = int | float | str | datetime


logger = logging.getLogger("org")


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

    if isinstance(expr, Sequence):
        return _evaluate_sequence(expr, stream, context)
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
    elif isinstance(expr, LetBinding):
        result = _evaluate_let_binding(expr, stream, context)
    elif isinstance(expr, IfElse):
        result = _evaluate_if_else(expr, stream, context)
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
    elif isinstance(expr, DictAssignment):
        result = _evaluate_dict_assignment(expr, stream, context)
    if result is not None:
        return result
    raise QueryRuntimeError("Unsupported expression type")


def _evaluate_sequence(expr: Sequence, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate left expression for side effects, then return right expression."""
    evaluate_expr(expr.first, stream, context)
    return evaluate_expr(expr.second, stream, context)


def _evaluate_dict_assignment(
    expr: DictAssignment,
    stream: Stream,
    context: EvalContext,
) -> Stream:
    """Evaluate dictionary field assignment expressions."""
    output = _stream()
    for item in stream:
        base_values = evaluate_expr(expr.base, _stream([item]), context)
        key_values = evaluate_expr(expr.key_expr, _stream([item]), context)
        value_values = evaluate_expr(expr.value, _stream([item]), context)

        key_base_pairs = _broadcast(key_values, base_values)
        value_key_base_pairs = _broadcast(value_values, _stream(key_base_pairs))
        for value, key_base_pair in value_key_base_pairs:
            key, base = cast(tuple[object, object], key_base_pair)
            if not isinstance(base, dict):
                raise QueryRuntimeError("Assignment target must evaluate to a dictionary")
            if not isinstance(key, str):
                raise QueryRuntimeError("Assignment key must evaluate to a string")
            base[key] = value
            output.append(base)
    return output


def _evaluate_as_binding(expr: AsBinding, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate variable binding and pass through bound values."""
    bound_values = evaluate_expr(expr.source, stream, context)
    bound_value = bound_values[0] if len(bound_values) == 1 else bound_values
    context.variables[expr.name] = bound_value
    return bound_values


def _evaluate_let_binding(expr: LetBinding, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate let-binding with scoped variable lifetime."""
    output = _stream()
    had_previous = expr.name in context.variables
    previous_value = context.variables.get(expr.name)

    for item in stream:
        bound_values = evaluate_expr(expr.value, _stream([item]), context)
        bound_value: object = bound_values[0] if len(bound_values) == 1 else bound_values

        context.variables[expr.name] = bound_value
        output.extend(evaluate_expr(expr.body, _stream([item]), context))

    if had_previous:
        context.variables[expr.name] = previous_value
    else:
        context.variables.pop(expr.name, None)
    return output


def _evaluate_if_else(expr: IfElse, stream: Stream, context: EvalContext) -> Stream:
    """Evaluate conditional expressions per input stream item."""
    output = _stream()
    for item in stream:
        condition_values = evaluate_expr(expr.condition, _stream([item]), context)
        branch = (
            expr.then_expr if any(bool(value) for value in condition_values) else expr.else_expr
        )
        output.extend(evaluate_expr(branch, _stream([item]), context))
    return output


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
    return _normalize_org_date_value(attr_value)


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
                return _normalize_org_date_value(base[key])
            return None
        raise QueryRuntimeError("Index access requires a list, tuple, or string")
    raise QueryRuntimeError("Bracket key must be a string or integer")


def _normalize_org_date_value(value: object) -> object:
    """Normalize empty org date objects to none."""
    if isinstance(value, OrgDate) and not bool(value):
        return None
    return value


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
        return _apply_compare(operator, left, right)
    if operator == "matches":
        if not isinstance(left, str) or not isinstance(right, str):
            raise QueryRuntimeError("matches operator requires two strings")
        # FIXME Potentially recompiles the same regex multiple times when broadcasting a scalar to stream.
        return bool(re.compile(right).search(left))
    if operator in {"and", "or"}:
        return _apply_boolean(operator, left, right)
    if operator == "in":
        return _apply_in_operator(left, right)
    if operator in {"**", "*", "/", "+", "-", "mod", "rem", "quot"}:
        return _apply_numeric_operator(operator, left, right)
    raise QueryRuntimeError(f"Unsupported operator: {operator}")


def _apply_numeric_operator(operator: str, left: object, right: object) -> object:
    """Apply numeric operators with arithmetic semantics."""
    extended_result = _apply_extended_non_numeric_operator(operator, left, right)
    if extended_result is not _OPERATOR_NOT_HANDLED:
        return extended_result

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


def _apply_extended_non_numeric_operator(operator: str, left: object, right: object) -> object:
    """Apply supported string and collection operators."""
    if operator == "*" and isinstance(left, str):
        if not isinstance(right, int):
            raise QueryRuntimeError("* operator requires integer multiplier for string operands")
        return left * right

    if operator == "+" and isinstance(left, str) and isinstance(right, str):
        return left + right

    if operator == "+" and _is_collection_value(left):
        return _append_to_collection(left, right)

    if operator == "-" and _is_collection_value(left):
        return _subtract_from_collection(left, right)

    return _OPERATOR_NOT_HANDLED


def _apply_simple_numeric_operator(operator: str, left: int | float, right: int | float) -> object:
    """Apply non-dividing numeric operators."""
    operations: dict[str, object] = {
        "**": left**right,
        "*": left * right,
        "+": left + right,
        "-": left - right,
    }
    return operations[operator]


def _is_collection_value(value: object) -> bool:
    """Return whether value is a mutable-like query collection."""
    return isinstance(value, (list, tuple, set))


def _append_to_collection(collection: object, value: object) -> object:
    """Append one value while preserving collection type."""
    values_to_add = list(value) if isinstance(value, (list, tuple, set)) else [value]
    if isinstance(collection, list):
        return [*collection, *values_to_add]
    if isinstance(collection, tuple):
        return (*collection, *values_to_add)
    if isinstance(collection, set):
        return {*collection, *values_to_add}
    raise QueryRuntimeError("Collection append requires list, tuple, or set")


def _subtract_from_collection(collection: object, value: object) -> object:
    """Subtract scalar or collection values while preserving left ordering/type."""
    to_remove = list(value) if isinstance(value, (list, tuple, set)) else [value]

    def should_keep(candidate: object) -> bool:
        return all(candidate != removed for removed in to_remove)

    if isinstance(collection, list):
        return [item for item in collection if should_keep(item)]
    if isinstance(collection, tuple):
        return tuple(item for item in collection if should_keep(item))
    if isinstance(collection, set):
        return {item for item in collection if should_keep(item)}
    raise QueryRuntimeError("Collection subtraction requires list, tuple, or set")


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
    if isinstance(left, OrgDate) and isinstance(right, OrgDate):
        left = _org_date_start_for_comparison(left)
        right = _org_date_start_for_comparison(right)
    if operator == "==":
        return left == right
    return left != right


def _apply_boolean(operator: str, left: object, right: object) -> object:
    """Apply boolean operators with query-language truthiness."""
    if operator == "and":
        return bool(left) and bool(right)
    return left if bool(left) else right


def _apply_compare(operator: str, left: object, right: object) -> bool:
    """Apply numeric, string, or OrgDate comparison operators."""
    if left is None or right is None:
        if operator in {">", "<"}:
            return False
        return left is None and right is None

    is_org_date = isinstance(left, OrgDate) and isinstance(right, OrgDate)
    is_numeric = isinstance(left, (int, float)) and isinstance(right, (int, float))
    is_string = isinstance(left, str) and isinstance(right, str)
    if not is_org_date and not is_numeric and not is_string:
        raise QueryRuntimeError("Comparison operators require numeric, string, or OrgDate operands")
    if is_org_date:
        left_date = _org_date_start_for_comparison(cast(OrgDate, left))
        right_date = _org_date_start_for_comparison(cast(OrgDate, right))
        return _apply_compare_datetime(operator, left_date, right_date)
    if is_numeric:
        left_value_num = cast(float | int, left)
        right_value_num = cast(float | int, right)
        return _apply_compare_numeric(operator, left_value_num, right_value_num)
    left_value_str = cast(str, left)
    right_value_str = cast(str, right)
    return _apply_compare_string(operator, left_value_str, right_value_str)


def _apply_compare_numeric(operator: str, left: float | int, right: float | int) -> bool:
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


def _apply_compare_string(operator: str, left: str, right: str) -> bool:
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


def _apply_compare_datetime(operator: str, left: datetime, right: datetime) -> bool:
    """Apply datetime comparisons."""
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    raise QueryRuntimeError(f"Unsupported comparison operator: {operator}")


def _org_date_start_for_comparison(value: OrgDate) -> datetime:
    """Return OrgDate start normalized for comparisons."""
    if value.start is None:
        raise QueryRuntimeError("Comparison operators require OrgDate values with start")
    if isinstance(value.start, datetime):
        return value.start
    return datetime(value.start.year, value.start.month, value.start.day)


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
    no_arg_functions: dict[str, Callable[[Stream], Stream]] = {
        "reverse": _func_reverse,
        "unique": _func_unique,
        "length": _func_length,
        "sum": _func_sum,
        "max": _func_max,
        "min": _func_min,
        "type": _func_type,
        "sha256": _func_sha256,
        "uuid": _func_uuid,
        "debug": _func_debug,
    }
    arg_functions: dict[str, Callable[[Stream, Expr, EvalContext], Stream]] = {
        "str": _func_str,
        "int": _func_int,
        "float": _func_float,
        "bool": _func_bool,
        "ts": _func_ts,
        "match": _func_match,
        "select": _func_select,
        "sort_by": _func_sort_by,
        "join": _func_join,
        "map": _func_map,
        "not": _func_not,
        "timestamp": _func_timestamp,
        "clock": _func_clock,
        "repeated_task": _func_repeated_task,
    }

    if expr.name in no_arg_functions:
        if expr.argument is not None:
            raise QueryRuntimeError(f"{expr.name} does not accept an argument")
        return no_arg_functions[expr.name](stream)

    if expr.name in arg_functions:
        if expr.argument is None:
            raise QueryRuntimeError(f"{expr.name} requires an argument")
        return arg_functions[expr.name](stream, expr.argument, context)

    available = ", ".join(sorted({*no_arg_functions, *arg_functions}))
    raise QueryRuntimeError(f"Unsupported function: {expr.name}. Available functions: {available}")


def _type_name(value: object) -> str:
    """Return user-facing type name for query values."""
    if value is None:
        return "none"
    return type(value).__name__


def _argument_expressions(argument: Expr) -> tuple[Expr, ...]:
    """Return function argument expressions as a tuple."""
    if isinstance(argument, TupleExpr):
        return argument.items
    return (argument,)


def _iter_function_argument_values(
    stream: Stream,
    argument: Expr,
    context: EvalContext,
) -> Iterable[tuple[object, ...]]:
    """Yield evaluated argument combinations per input item."""
    arg_exprs = _argument_expressions(argument)
    for item in stream:
        arg_parts = [evaluate_expr(part, _stream([item]), context) for part in arg_exprs]
        if any(len(part) == 0 for part in arg_parts):
            continue
        yield from product(*arg_parts)


def _ensure_arity(arguments: tuple[object, ...], expected: set[int], function_name: str) -> None:
    """Ensure function receives one of supported arities."""
    if len(arguments) in expected:
        return
    allowed = ", ".join(str(value) for value in sorted(expected))
    raise QueryRuntimeError(f"{function_name} expects {allowed} argument(s)")


def _parse_org_date(value: object) -> OrgDate:
    """Convert runtime value into an OrgDate object."""
    if isinstance(value, OrgDate):
        return value
    if not isinstance(value, str):
        raise QueryRuntimeError("timestamp values must evaluate to string, OrgDate, or none")

    parsed_values = OrgDate.list_from_str(value)
    if parsed_values:
        return parsed_values[0]

    fallback = OrgDate.from_str(value)
    if fallback.start is None:
        raise QueryRuntimeError(f"Cannot parse timestamp: {value}")
    return fallback


def _as_org_date_or_none(value: object) -> OrgDate | None:
    """Convert optional timestamp value into OrgDate or none."""
    if value is None:
        return None
    return _parse_org_date(value)


def _as_active_or_none(value: object) -> bool | None:
    """Convert optional active value into bool or none."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise QueryRuntimeError("active value must evaluate to boolean or none")


def _as_state_or_none(value: object, field_name: str) -> str | None:
    """Convert optional state value into string or none."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise QueryRuntimeError(f"{field_name} value must evaluate to string or none")


def _func_type(stream: Stream) -> Stream:
    """Return type names for stream values."""
    return _stream([_type_name(value) for value in stream])


def _func_uuid(stream: Stream) -> Stream:
    """Return one UUIDv4 value per input stream item."""
    return _stream([str(uuid4()) for _item in stream])


def _func_debug(stream: Stream) -> Stream:
    """Log each input value and return the input stream unchanged."""
    for value in stream:
        logger.info("%s", value)
    return stream


def _func_str(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Convert argument values into strings."""
    output = _stream()
    for item in stream:
        argument_values = evaluate_expr(argument, _stream([item]), context)
        output.extend(str(value) for value in argument_values)
    return output


def _func_int(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Convert argument values into integers."""
    output = _stream()
    for item in stream:
        argument_values = evaluate_expr(argument, _stream([item]), context)
        for value in argument_values:
            output.append(_convert_to_int(value))
    return output


def _func_float(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Convert argument values into floats."""
    output = _stream()
    for item in stream:
        argument_values = evaluate_expr(argument, _stream([item]), context)
        for value in argument_values:
            output.append(_convert_to_float(value))
    return output


def _func_bool(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Convert argument values into booleans."""
    output = _stream()
    for item in stream:
        argument_values = evaluate_expr(argument, _stream([item]), context)
        for value in argument_values:
            output.append(_convert_to_bool(value))
    return output


def _func_ts(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Convert argument values into OrgDate timestamps."""
    output = _stream()
    for item in stream:
        argument_values = evaluate_expr(argument, _stream([item]), context)
        for value in argument_values:
            output.append(_parse_org_date(value))
    return output


def _func_sha256(stream: Stream) -> Stream:
    """Hash each input string value with SHA-256."""
    output = _stream()
    for value in stream:
        if not isinstance(value, str):
            raise QueryRuntimeError("sha256 requires string input values")
        output.append(sha256(value.encode("utf-8")).hexdigest())
    return output


def _func_match(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Match input strings against regex argument values."""
    output = _stream()
    for item in stream:
        if not isinstance(item, str):
            raise QueryRuntimeError("match requires string input values")
        regex_values = evaluate_expr(argument, _stream([item]), context)
        for regex_value in regex_values:
            if not isinstance(regex_value, str):
                raise QueryRuntimeError("match requires string regex values")
            match_result = re.search(regex_value, item)
            if match_result is None:
                output.append(None)
                continue
            captures = [match_result.group(0), *list(match_result.groups())]
            output.append(captures)
    return output


def _convert_to_int(value: object) -> int:
    """Convert one value into integer with query typing rules."""
    if isinstance(value, bool):
        raise QueryRuntimeError("int accepts integer and string values")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise QueryRuntimeError(f"Cannot parse int: {value}") from exc
    raise QueryRuntimeError("int accepts integer and string values")


def _convert_to_float(value: object) -> float:
    """Convert one value into float with query typing rules."""
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise QueryRuntimeError(f"Cannot parse float: {value}") from exc
    raise QueryRuntimeError("float accepts float and string values")


def _convert_to_bool(value: object) -> bool:
    """Convert one value into bool with query typing rules."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise QueryRuntimeError(f"Cannot parse bool: {value}")
    raise QueryRuntimeError("bool accepts boolean and string values")


def _func_not(stream: Stream, condition: Expr, context: EvalContext) -> Stream:
    """Negate condition truthiness for each stream item."""
    output = _stream()
    for item in stream:
        condition_values = evaluate_expr(condition, _stream([item]), context)
        output.append(not any(bool(value) for value in condition_values))
    return output


def _func_timestamp(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Create OrgDate values from one, two, or three arguments."""
    output = _stream()
    for arguments in _iter_function_argument_values(stream, argument, context):
        _ensure_arity(arguments, {1, 2, 3}, "timestamp")
        start_date = _parse_org_date(arguments[0])

        if len(arguments) == 1:
            output.append(OrgDate(start_date.start, start_date.end, start_date.is_active()))
            continue

        end_date = _as_org_date_or_none(arguments[1])
        end_value = None if end_date is None else end_date.start

        if len(arguments) == 2:
            output.append(OrgDate(start_date.start, end_value, start_date.is_active()))
            continue

        active = _as_active_or_none(arguments[2])
        output.append(OrgDate(start_date.start, end_value, active))
    return output


def _func_clock(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Create OrgDateClock values from two or three arguments."""
    output = _stream()
    for arguments in _iter_function_argument_values(stream, argument, context):
        _ensure_arity(arguments, {2, 3}, "clock")
        start_date = _parse_org_date(arguments[0])
        end_date = _as_org_date_or_none(arguments[1])
        if end_date is None:
            raise QueryRuntimeError("clock end value cannot be none")
        clock_ctor: Callable[..., OrgDateClock] = OrgDateClock
        if len(arguments) == 2:
            output.append(clock_ctor(start_date.start, end_date.start))
            continue

        active = _as_active_or_none(arguments[2])
        output.append(clock_ctor(start_date.start, end_date.start, active=active))
    return output


def _func_repeated_task(stream: Stream, argument: Expr, context: EvalContext) -> Stream:
    """Create OrgDateRepeatedTask values from three or four arguments."""
    output = _stream()
    for arguments in _iter_function_argument_values(stream, argument, context):
        _ensure_arity(arguments, {3, 4}, "repeated_task")
        start_date = _parse_org_date(arguments[0])
        before = _as_state_or_none(arguments[1], "before")
        after = _as_state_or_none(arguments[2], "after")

        if len(arguments) == 3:
            output.append(
                OrgDateRepeatedTask(start_date.start, cast(str, before), cast(str, after))
            )
            continue

        active = _as_active_or_none(arguments[3])
        output.append(
            OrgDateRepeatedTask(
                start_date.start, cast(str, before), cast(str, after), active=active
            )
        )
    return output


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


def _func_max(stream: Stream) -> Stream:
    """Return maximal value for each collection in stream."""
    return _stream([_collection_extreme(value, "max") for value in stream])


def _func_min(stream: Stream) -> Stream:
    """Return minimal value for each collection in stream."""
    return _stream([_collection_extreme(value, "min") for value in stream])


def _collection_extreme(value: object, mode: str) -> object:
    """Return min or max value from one collection input."""
    collection = _extract_collection(value)
    if len(collection) == 0:
        return None

    filtered_collection = [item for item in collection if item is not None]
    if len(filtered_collection) == 0:
        return None

    comparable_values = [_to_comparable_value(item) for item in filtered_collection]
    categories = {category for category, _key in comparable_values}
    if len(categories) != 1:
        raise QueryRuntimeError(f"{mode} requires collection items of one comparable type")
    category = next(iter(categories))

    best_key: ComparableKey | None = None
    best_item: object | None = None
    for index, ((_, item_key), item_value) in enumerate(
        zip(comparable_values, filtered_collection, strict=True)
    ):
        if index == 0:
            best_key = item_key
            best_item = item_value
            continue

        if best_key is None:
            raise QueryRuntimeError(f"{mode} requires comparable values")

        if _is_better_item(mode, category, item_key, best_key):
            best_key = item_key
            best_item = item_value

    if best_item is None:
        raise QueryRuntimeError(f"{mode} requires non-empty collections")
    return best_item


def _to_comparable_value(value: object) -> tuple[str, ComparableKey]:
    """Convert one value into a typed comparison key."""
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, datetime):
        return ("date", value)
    if isinstance(value, date):
        return ("date", datetime(value.year, value.month, value.day))
    if isinstance(value, OrgDate):
        if value.start is None:
            raise QueryRuntimeError("max/min cannot compare OrgDate with empty start")
        return _to_comparable_value(value.start)
    raise QueryRuntimeError(f"max/min cannot compare value of type {type(value).__name__}")


def _is_better_item(
    mode: str,
    category: str,
    candidate: ComparableKey,
    current: ComparableKey,
) -> bool:
    """Return whether candidate should replace current min/max item."""
    if category == "number":
        candidate_number = cast(int | float, candidate)
        current_number = cast(int | float, current)
        return (
            candidate_number > current_number
            if mode == "max"
            else candidate_number < current_number
        )

    if category == "string":
        candidate_string = cast(str, candidate)
        current_string = cast(str, current)
        return (
            candidate_string > current_string
            if mode == "max"
            else candidate_string < current_string
        )

    if category == "date":
        candidate_date = cast(datetime, candidate)
        current_date = cast(datetime, current)
        return candidate_date > current_date if mode == "max" else candidate_date < current_date

    raise QueryRuntimeError(f"max/min unsupported comparable category: {category}")


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
    with_key: list[tuple[ComparableKey, object]] = []
    without_key: list[object] = []
    key_category: str | None = None

    for _, item in enumerate(stream):
        key_values = evaluate_expr(key_expr, _stream([item]), context)
        key = _normalize_org_date_value(key_values[0] if key_values else None)
        if key is None:
            without_key.append(item)
            continue

        category, comparable_key = _to_comparable_value(key)
        if key_category is None:
            key_category = category
        elif key_category != category:
            raise QueryRuntimeError("sort_by requires keys of one comparable type")
        with_key.append((comparable_key, item))

    ordered_with_key = _sort_with_key_entries(with_key, key_category)
    return _stream([*ordered_with_key, *without_key])


def _sort_with_key_entries(
    entries: list[tuple[ComparableKey, object]],
    category: str | None,
) -> list[object]:
    """Sort key-bearing entries by comparable key descending."""
    if not entries or category is None:
        return [item for _, item in entries]

    return [item for _, item in sorted(entries, key=lambda value: value[0], reverse=True)]


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
