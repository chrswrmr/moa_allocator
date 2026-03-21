## 1. Tree Walker

- [x] 1.1 Implement `_collect_nodes(node: dict) -> list[dict]` — recursive depth-first walk that collects every node dict from the `root_node` tree (handles `children`, `true_branch`, `false_branch`)
- [x] 1.2 Verify that `settings` node is included in the collected set for UUID uniqueness (the settings `id` participates in uniqueness)

## 2. Semantic Validation Rules

- [x] 2.1 Implement UUID uniqueness check — collect all `id` values from settings + all tree nodes; raise `DSLValidationError` on first duplicate
- [x] 2.2 Implement defined-weight completeness check — for each `weight` node with `method == "defined"`, verify `custom_weights` keys == set of child `id`s (no missing, no extra)
- [x] 2.3 Implement defined-weight sum check — verify `custom_weights` values sum to `1.0 ± 0.001`; raise `DSLValidationError` with the weight node's `id` and `name`
- [x] 2.4 Implement filter count bound check — for each `filter` node, verify `select.count >= 1` and `select.count <= len(children)`
- [x] 2.5 Implement lookback-required check — for every conditionMetric (`lhs`, `rhs` in `if_else` conditions) and sortMetric (`sort_by` in `filter`) where `function != "current_price"`, verify `lookback` is present
- [x] 2.6 Implement date ordering check — parse `settings.start_date` and `settings.end_date` as `date` objects; raise `DSLValidationError(node_id="root", node_name="settings", ...)` if `start_date >= end_date`
- [x] 2.7 Implement rebalance threshold range check — if `rebalance_threshold` is present in settings, verify `0 < value < 1`; raise `DSLValidationError(node_id="root", node_name="settings", ...)`

## 3. Wire Into Pipeline

- [x] 3.1 Define `_validate_semantics(doc: dict) -> None` in `compiler.py` that calls each rule in order
- [x] 3.2 Replace the `NotImplementedError` stub in `compile_strategy()` with a call to `_validate_semantics(doc)` at Step 3, keeping the `NotImplementedError` for Steps 4–5 (node instantiation, C4's responsibility)

## 4. Tests

- [x] 4.1 Test UUID uniqueness — valid (all unique) and invalid (duplicate across settings + tree nodes)
- [x] 4.2 Test defined-weight completeness — missing key, extra key, exact match
- [x] 4.3 Test defined-weight sum — sum < 0.999, sum > 1.001, sum within tolerance (0.999–1.001)
- [x] 4.4 Test filter count bound — count < 1 (caught by schema), count > len(children), count == len(children) (valid)
- [x] 4.5 Test lookback required — each non-`current_price` function missing lookback; `current_price` without lookback (valid); valid metric with lookback
- [x] 4.6 Test date ordering — start < end (valid), start == end (invalid), start > end (invalid)
- [x] 4.7 Test rebalance threshold — absent (valid), 0.5 (valid), 0.0 (invalid), 1.0 (invalid), negative (invalid)
- [x] 4.8 Run `uv run pytest` — all tests pass
