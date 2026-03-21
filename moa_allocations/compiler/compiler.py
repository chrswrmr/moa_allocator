from __future__ import annotations

import json
from importlib import resources

import jsonschema

from moa_allocations.exceptions import DSLValidationError

_DSL_VERSION = "1.0.0"


def _load_schema() -> dict:
    ref = resources.files("moa_allocations.compiler.schema").joinpath("moa_DSL_schema.json")
    with ref.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    settings = doc["settings"]
    root_node = doc["root_node"]

    raise NotImplementedError(
        f"compile_strategy: steps 3-5 (semantic validation, node instantiation) not yet implemented "
        f"[id={strategy_id}, version-dsl={version_dsl}]"
    )
