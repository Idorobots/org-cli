"""Task ordering specifications and utilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import orgparse
import typer

from org.cli_common import get_most_recent_timestamp
from org.filters import get_gamify_exp


@dataclass(frozen=True)
class OrderSpec:
    """Ordering specification for task lists."""

    key: Callable[[orgparse.node.OrgNode], float | int | None]
    direction: int
    label: str


def _timestamp_value(node: orgparse.node.OrgNode) -> float | None:
    timestamp = get_most_recent_timestamp(node)
    return timestamp.timestamp() if timestamp else None


def _gamify_exp_value(node: orgparse.node.OrgNode) -> int | None:
    return get_gamify_exp(node)


def _level_value(node: orgparse.node.OrgNode) -> int | None:
    level = node.level
    if level is None:
        return None
    return cast(int, level)


def _constant_value(_: orgparse.node.OrgNode) -> int:
    return 0


ORDER_SPECS: dict[str, OrderSpec] = {
    "file-order": OrderSpec(
        key=_constant_value,
        direction=1,
        label="file order",
    ),
    "file-order-reverse": OrderSpec(
        key=_constant_value,
        direction=1,
        label="file order reversed",
    ),
    "file-order-reversed": OrderSpec(
        key=_constant_value,
        direction=1,
        label="file order reversed",
    ),
    "timestamp-asc": OrderSpec(
        key=_timestamp_value,
        direction=1,
        label="most recent timestamp ascending",
    ),
    "timestamp-desc": OrderSpec(
        key=_timestamp_value,
        direction=-1,
        label="most recent timestamp descending",
    ),
    "gamify-exp-asc": OrderSpec(
        key=_gamify_exp_value,
        direction=1,
        label="gamify_exp ascending",
    ),
    "gamify-exp-desc": OrderSpec(
        key=_gamify_exp_value,
        direction=-1,
        label="gamify_exp descending",
    ),
    "level": OrderSpec(
        key=_level_value,
        direction=1,
        label="level ascending",
    ),
}


def normalize_order_by(order_by: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize order_by values into a list."""
    if order_by is None:
        return []
    if isinstance(order_by, list):
        return order_by
    if isinstance(order_by, tuple):
        return list(order_by)
    return [order_by]


def validate_order_by(order_by: list[str]) -> None:
    """Validate order_by values."""
    invalid = [value for value in order_by if value not in ORDER_SPECS]
    if not invalid:
        return

    supported = ", ".join(ORDER_SPECS)
    invalid_list = ", ".join(invalid)
    raise typer.BadParameter(f"--order-by must be one of: {supported}\nGot: {invalid_list}")


def order_nodes(
    nodes: list[orgparse.node.OrgNode],
    order_by: list[str],
) -> list[orgparse.node.OrgNode]:
    """Order nodes using the selected order criteria in sequence."""
    validate_order_by(order_by)
    ordered_nodes = list(nodes)

    for order_value in order_by:
        if order_value == "file-order":
            continue
        if order_value in {"file-order-reverse", "file-order-reversed"}:
            ordered_nodes.reverse()
            continue

        order_spec = ORDER_SPECS[order_value]
        key_fn = order_spec.key
        direction = order_spec.direction

        def sort_key(
            node: orgparse.node.OrgNode,
            key_func: Callable[[orgparse.node.OrgNode], float | int | None] = key_fn,
            direction_value: int = direction,
        ) -> tuple[int, float | int]:
            value = key_func(node)
            if value is None:
                return (1, 0)
            return (0, direction_value * value)

        ordered_nodes = sorted(ordered_nodes, key=sort_key)

    return ordered_nodes
