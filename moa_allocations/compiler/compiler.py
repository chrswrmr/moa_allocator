from __future__ import annotations

import json
from datetime import date
from importlib import resources

import jsonschema

from moa_allocations.exceptions import DSLValidationError

_DSL_VERSION = "1.0.0"

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


def compile_strategy(path: str):
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
    strategy_id = doc["id"]
    version_dsl = doc["version-dsl"]

    # Step 3: semantic validation
    _validate_semantics(doc)

    raise NotImplementedError(
        f"compile_strategy: steps 4-5 (node instantiation) not yet implemented "
        f"[id={strategy_id}, version-dsl={version_dsl}]"
    )
