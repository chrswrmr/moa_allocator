## 1. SelectTopN and SelectBottomN

- [x] 1.1 Add private `_rank_and_select(target, n, metric, lookback, reverse)` helper in `selection.py` — reads child series from `target.perm`, calls `compute_metric()`, excludes NaN results, sorts by metric value (stable), selects top n, writes ids to `target.temp['selected']`, returns True/False
- [x] 1.2 Implement `SelectTopN(n, metric, lookback)` class — calls `_rank_and_select` with `reverse=True`
- [x] 1.3 Implement `SelectBottomN(n, metric, lookback)` class — calls `_rank_and_select` with `reverse=False`
- [x] 1.4 Handle n > len(children) edge case — select all available children

## 2. WeightInvVol

- [x] 2.1 Implement `WeightInvVol(lookback)` class in `weighting.py` — reads selected children from `target.temp['selected']`, computes `std_dev_return` via `compute_metric()` for each, excludes zero/NaN vol children
- [x] 2.2 Compute raw weights as `1.0 / vol[i]`, normalise to sum to 1.0, write to `target.temp['weights']`
- [x] 2.3 Return `False` if all children are excluded (zero/NaN vol), `True` otherwise

## 3. Tests — SelectTopN / SelectBottomN

- [x] 3.1 Test normal descending ranking — 5 children, n=3, verify correct top-3 ids selected
- [x] 3.2 Test normal ascending ranking — 4 children, n=2, verify correct bottom-2 ids selected
- [x] 3.3 Test n > len(children) — all children selected, returns True
- [x] 3.4 Test NaN exclusion — 2 of 5 children have insufficient history, verify ranking over remaining 3
- [x] 3.5 Test all-NaN — all children have insufficient history, verify returns False
- [x] 3.6 Test stable sort on tied metric values — verify child order from `children` list is preserved

## 4. Tests — WeightInvVol

- [x] 4.1 Test normal inverse-vol weighting — 3 children with known vol values, verify weights and sum to 1.0
- [x] 4.2 Test single selected child — weight must be 1.0
- [x] 4.3 Test zero-vol child excluded — verify redistribution to remaining children
- [x] 4.4 Test NaN-vol child excluded — verify redistribution to remaining children
- [x] 4.5 Test all children excluded (all zero/NaN vol) — verify returns False

## 5. Verification

- [x] 5.1 Run `uv run pytest` — all tests pass
