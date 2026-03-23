from __future__ import annotations

import json
import re
from datetime import date
from importlib import resources

import jsonschema

from moa_allocations.engine.node import AssetNode, FilterNode, IfElseNode, StrategyNode, WeightNode
from moa_allocations.engine.strategy import RootNode, Settings
from moa_allocations.exceptions import DSLValidationError

_DSL_VERSION = "1.0.0"

_LOOKBACK_MULTIPLIERS = {"d": 1}
_LOOKBACK_RE = re.compile(r"^(\d+)(d)$")


def _convert_lookback(time_offset: str) -> int:
    """Convert a time_offset string (e.g. '200d') to integer trading days."""
    m = _LOOKBACK_RE.match(time_offset)
    if not m:
        raise DSLValidationError(
            node_id="root",
            node_name="",
            message=f"invalid time_offset format '{time_offset}'; expected pattern like '200d'",
        )
    amount, unit = int(m.group(1)), m.group(2)
    return amount * _LOOKBACK_MULTIPLIERS[unit]


def _build_settings(raw: dict) -> Settings:
    """Construct a Settings dataclass from the validated settings dict."""
    return Settings(
        id=raw["id"],
        name=raw["name"],
        starting_cash=float(raw["starting_cash"]),
        start_date=date.fromisoformat(raw["start_date"]),
        end_date=date.fromisoformat(raw["end_date"]),
        slippage=float(raw.get("slippage", 0.0005)),
        fees=float(raw.get("fees", 0.0)),
        rebalance_frequency=raw["rebalance_frequency"],
        rebalance_threshold=raw.get("rebalance_threshold"),
    )


def _build_metric(metric: dict) -> dict:
    """Return a copy of a conditionMetric or sortMetric with lookback converted to int."""
    result = dict(metric)
    if "lookback" in result:
        result["lookback"] = _convert_lookback(result["lookback"])
    return result


def _build_condition(cond: dict) -> dict:
    """Return a copy of a condition dict with all time_offsets converted to int."""
    result = dict(cond)
    result["lhs"] = _build_metric(result["lhs"])
    if isinstance(result.get("rhs"), dict):
        result["rhs"] = _build_metric(result["rhs"])
    duration_str = result.get("duration", "1d")
    result["duration"] = _convert_lookback(duration_str)
    return result


def _build_node(raw: dict) -> StrategyNode | AssetNode:
    """Recursively instantiate a node dict into the C1 node class hierarchy."""
    node_type = raw.get("type")
    node_id = raw["id"]
    node_name = raw.get("name")

    if node_type == "asset":
        return AssetNode(id=node_id, ticker=raw["ticker"], name=node_name)

    if node_type == "weight":
        children = [_build_node(c) for c in raw.get("children", [])]
        method_params = dict(raw.get("method_params", {}))
        if "lookback" in method_params:
            method_params["lookback"] = _convert_lookback(method_params["lookback"])
        if "custom_weights" in method_params:
            method_params["weights"] = method_params.pop("custom_weights")
        return WeightNode(
            id=node_id,
            method=raw["method"],
            method_params=method_params,
            children=children,
            name=node_name,
        )

    if node_type == "filter":
        children = [_build_node(c) for c in raw.get("children", [])]
        sort_by = _build_metric(raw["sort_by"])
        return FilterNode(
            id=node_id,
            sort_by=sort_by,
            select=raw["select"],
            children=children,
            name=node_name,
        )

    if node_type == "if_else":
        conditions = [_build_condition(c) for c in raw.get("conditions", [])]
        true_branch = _build_node(raw["true_branch"])
        false_branch = _build_node(raw["false_branch"])
        return IfElseNode(
            id=node_id,
            logic_mode=raw["logic_mode"],
            conditions=conditions,
            true_branch=true_branch,
            false_branch=false_branch,
            name=node_name,
        )

    raise DSLValidationError(
        node_id=node_id,
        node_name=node_name or "",
        message=f"unknown node type '{node_type}'",
    )


_LOOKBACK_REQUIRED = {
    "cumulative_return",
    "ema_price",
    "sma_price",
    "sma_return",
    "max_drawdown",
    "rsi",
    "std_dev_price",
    "std_dev_return",
}


def _load_schema() -> dict:
    ref = resources.files("moa_allocations.compiler.schema").joinpath("moa_DSL_schema.json")
    with ref.open("r", encoding="utf-8") as f:
        return json.load(f)


def _collect_nodes(node: dict) -> list[dict]:
    """Depth-first walk — returns every node in the subtree rooted at `node`."""
    nodes = [node]
    for child in node.get("children", []):
        nodes.extend(_collect_nodes(child))
    if "true_branch" in node:
        nodes.extend(_collect_nodes(node["true_branch"]))
    if "false_branch" in node:
        nodes.extend(_collect_nodes(node["false_branch"]))
    return nodes


def _validate_semantics(doc: dict) -> None:
    """Run semantic checks after JSON Schema validation passes. Raises DSLValidationError on any violation."""
    settings = doc["settings"]
    all_nodes = _collect_nodes(doc["root_node"])

    # --- UUID uniqueness (settings id + all tree node ids) ---
    seen: dict[str, str] = {settings["id"]: settings.get("name", "")}
    for node in all_nodes:
        node_id = node["id"]
        node_name = node.get("name", "")
        if node_id in seen:
            raise DSLValidationError(
                node_id=node_id,
                node_name=node_name,
                message=f"duplicate node id '{node_id}' (also used by '{seen[node_id]}')",
            )
        seen[node_id] = node_name

    # --- Defined weight completeness and sum ---
    for node in all_nodes:
        if node.get("type") == "weight" and node.get("method") == "defined":
            node_id = node["id"]
            node_name = node.get("name", "")
            children_ids = {c["id"] for c in node.get("children", [])}
            custom_weights: dict = node.get("method_params", {}).get("custom_weights", {})
            custom_keys = set(custom_weights.keys())
            if custom_keys != children_ids:
                missing = children_ids - custom_keys
                extra = custom_keys - children_ids
                parts = []
                if missing:
                    parts.append(f"missing keys: {sorted(missing)}")
                if extra:
                    parts.append(f"extra keys: {sorted(extra)}")
                raise DSLValidationError(
                    node_id=node_id,
                    node_name=node_name,
                    message=f"custom_weights keys do not match children ids — {'; '.join(parts)}",
                )
            total = sum(custom_weights.values())
            if abs(total - 1.0) > 0.001:
                raise DSLValidationError(
                    node_id=node_id,
                    node_name=node_name,
                    message=f"custom_weights sum to {total:.6f}, expected 1.0 ± 0.001",
                )

    # --- Filter select count bound ---
    for node in all_nodes:
        if node.get("type") == "filter":
            node_id = node["id"]
            node_name = node.get("name", "")
            count = node["select"]["count"]
            n_children = len(node.get("children", []))
            if count > n_children:
                raise DSLValidationError(
                    node_id=node_id,
                    node_name=node_name,
                    message=f"select.count ({count}) exceeds children count ({n_children})",
                )

    # --- Lookback required for non-current_price metrics ---
    for node in all_nodes:
        node_id = node["id"]
        node_name = node.get("name", "")
        if node.get("type") == "if_else":
            for condition in node.get("conditions", []):
                for side in ("lhs", "rhs"):
                    metric = condition.get(side)
                    if isinstance(metric, dict) and metric.get("function") in _LOOKBACK_REQUIRED:
                        if "lookback" not in metric:
                            raise DSLValidationError(
                                node_id=node_id,
                                node_name=node_name,
                                message=f"metric function '{metric['function']}' requires 'lookback' (condition {side})",
                            )
        if node.get("type") == "filter":
            sort_by = node.get("sort_by", {})
            if sort_by.get("function") in _LOOKBACK_REQUIRED and "lookback" not in sort_by:
                raise DSLValidationError(
                    node_id=node_id,
                    node_name=node_name,
                    message=f"metric function '{sort_by['function']}' requires 'lookback' (sort_by)",
                )

    # --- Date ordering ---
    start = date.fromisoformat(settings["start_date"])
    end = date.fromisoformat(settings["end_date"])
    if start >= end:
        raise DSLValidationError(
            node_id="root",
            node_name="settings",
            message=f"start_date ({settings['start_date']}) must be before end_date ({settings['end_date']})",
        )

    # --- Rebalance threshold range ---
    threshold = settings.get("rebalance_threshold")
    if threshold is not None and not (0 < threshold < 1):
        raise DSLValidationError(
            node_id="root",
            node_name="settings",
            message=f"rebalance_threshold must be between 0 and 1 (exclusive), got {threshold}",
        )


def compile_strategy(path: str) -> RootNode:
    # Step 1: load and JSON-parse
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        raise DSLValidationError(node_id="root", node_name="settings", message=f"file not found: {path}")
    except json.JSONDecodeError as e:
        raise DSLValidationError(node_id="root", node_name="settings", message=f"invalid JSON: {e}")

    # Step 2a: version pre-check
    if "version-dsl" not in doc:
        raise DSLValidationError(node_id="root", node_name="settings", message="missing required field 'version-dsl'")
    if doc["version-dsl"] != _DSL_VERSION:
        raise DSLValidationError(
            node_id="root",
            node_name="settings",
            message=f"unsupported version-dsl '{doc['version-dsl']}', expected '{_DSL_VERSION}'",
        )

    # Step 2b: full schema validation
    schema = _load_schema()
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as e:
        raise DSLValidationError(node_id="root", node_name="settings", message=e.message)

    # Step 2c: extract top-level fields
    version_dsl = doc["version-dsl"]

    # Step 3: semantic validation
    _validate_semantics(doc)

    # Step 4: recursively instantiate the node tree
    root = _build_node(doc["root_node"])

    # Step 5: assemble and return the RootNode
    settings = _build_settings(doc["settings"])
    return RootNode(settings=settings, root=root, dsl_version=version_dsl)
