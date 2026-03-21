## Context

`compile_strategy()` in `compiler.py` currently ends at Step 2c (schema extraction) and raises `NotImplementedError`. Step 3 (semantic validation) and Steps 4–5 (node instantiation) are not yet implemented. C3 fills in Step 3 only; C4 handles instantiation.

The existing compiler already has the scaffolding: `doc`, `settings`, and `root_node` are all available after schema validation passes. The `DSLValidationError` exception class is defined and in use.

## Goals / Non-Goals

**Goals:**
- Implement `_validate_semantics(doc)` called between Step 2 and Step 4
- Enforce all seven semantic rules from `compiler.spec.md`
- Raise `DSLValidationError(node_id, node_name, message)` on the first violation encountered within each rule category
- Replace the `NotImplementedError` stub with a clean handoff to Step 4 (which C4 will fill)

**Non-Goals:**
- Node instantiation (C4)
- Runtime ticker availability checks (engine responsibility)
- Changes to `moa_DSL_schema.json`

## Decisions

### 1. Single-pass tree walk to collect all nodes

**Decision:** Walk the entire node tree once to collect all nodes into a flat list before applying any rule.

**Rationale:** UUID uniqueness and lookback checks both require visiting every node. A single recursive walk (depth-first) avoids walking the tree multiple times and keeps the code simple. The tree is small in practice (dozens of nodes at most), so performance is not a concern.

**Alternative considered:** Apply rules lazily during node instantiation in C4. Rejected because semantic validation must fully complete before instantiation begins (per the spec's pipeline ordering), and mixing concerns would complicate C4.

---

### 2. Rule ordering — fail-fast within each rule, collect all rule violations

**Decision:** Within a single rule (e.g., UUID uniqueness), raise `DSLValidationError` at the first violation. Do not attempt to aggregate multiple violations across rules.

**Rationale:** The spec says "each violation raises `DSLValidationError`" (singular). Fail-fast is simpler to implement and test, and matches user expectations for a compiler (one error at a time, fix-and-rerun workflow).

---

### 3. Implement as a private function `_validate_semantics(doc: dict) -> None`

**Decision:** Extract all semantic checks into a single private function that accepts the full parsed document.

**Rationale:** Keeps `compile_strategy()` readable as a high-level pipeline. The function raises on any violation and returns `None` on success — same error contract as the schema validator. No return value needed.

---

### 4. Node identity for error reporting

**Decision:** Each node has an `id` (UUID string) and optional `name`. Use `node.get("name", "")` — default to empty string when `name` is absent, consistent with how `DSLValidationError` is used in existing code.

**Rationale:** The spec requires `id` and `name` in every error. `name` is optional on nodes, so defaulting to `""` is safe.

---

### 5. `rebalance_threshold` range: `0 < value < 1`, not `0 <= value < 1`

**Decision:** Treat `rebalance_threshold = 0.0` as invalid (must be strictly > 0 if set).

**Rationale:** A threshold of exactly `0.0` means "always rebalance," which is indistinguishable from not setting the threshold at all. The spec says "if set > 0, rebalance only occurs when drift >= threshold" — a zero threshold would never filter any rebalance. Treating it as a user error prevents a confusing no-op config.

## Risks / Trade-offs

- **Incomplete node walk** → some semantic errors are missed silently. Mitigation: unit-test with deep nested trees, including nodes inside `true_branch`/`false_branch`.
- **`name` absent on a node** → `DSLValidationError` shows empty name, which is unhelpful but valid. Mitigation: accepted; the spec permits missing `name`.
- **Tight coupling of `_validate_semantics` to the raw dict structure** → if the DSL schema changes shape, the validator must change too. Mitigation: gated by `dsl-integrity.md` rule (ADR required before schema changes).
