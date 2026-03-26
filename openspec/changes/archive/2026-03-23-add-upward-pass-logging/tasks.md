## 1. Verify condition dict field names

- [x] 1.1 Read `openspec/moa_strategy_DSL/moa_Req_to_DSL.md` and confirm the field names used in IfElseNode condition dicts (lhs/rhs keys: `asset`, `metric`, `lookback`, `operator`)
- [x] 1.2 Confirm the compiled condition dict structure matches by reading `moa_allocations/engine/node.py` IfElseNode definition and `moa_allocations/compiler/compiler.py` condition compilation

## 2. Add UPWARD pass boundary logging

- [x] 2.1 In `_upward_pass()` (runner.py), add `logger.debug` call before the node loop: emit `"UPWARD  start  date=%s  t=%d"` with `extra={"keyword": "UPWARD", "text": "start", "date": date_str, "t_idx": t_idx}`
- [x] 2.2 Thread `date_str` into `_upward_pass()` — update signature to `_upward_pass(self, t_idx: int, date_str: str = "")` and update the call site in `run()`

## 3. Implement WeightNode detail formatter

- [x] 3.1 Add module-level helper `_log_upward_weight(node, weights, t_idx, nav_val, runner)` in runner.py
- [x] 3.2 Build the `┌─` header line: `node=<name>  type=weight-<method>  NodeName = <name>  id=<id>`
- [x] 3.3 For each child_id in weights: resolve child NAV (asset → price_data, strategy → nav_array[t_idx]), build `│  ← NAV <child_name> nav= <nav_value>  w=<weight>  id=<child_id>` line
- [x] 3.4 Add `│  NAV node  t=<t_idx>  nav=<calculated_nav>` line and `└─` footer, emit as single `logger.debug` call

## 4. Implement FilterNode detail formatter

- [x] 4.1 Add module-level helper `_log_upward_filter(node, weights, t_idx, nav_val, runner)` in runner.py
- [x] 4.2 Build header: `node=<name>  type=filter-<mode><count>  NodeName = <name>  id=<id>`
- [x] 4.3 Add config line: `│  Config: metric=<metric_name>  lookback=<days>`
- [x] 4.4 For each child in `node.children`: if child_id in weights → `│  ↓ NAV <name> nav= <value>  w=<weight>  id=<id>`, else → `│  ✗ NAV <name> nav= <value>  id=<id>  [dropped]`
- [x] 4.5 Add NAV node line and `└─` footer, emit as single `logger.debug` call

## 5. Implement IfElseNode detail formatter

- [x] 5.1 Add module-level helper `_log_upward_ifelse(node, weights, t_idx, nav_val, runner)` in runner.py
- [x] 5.2 Build header: `type=if_else  logic_mode=<AND|OR>  NodeName = <name>  id=<id>`
- [x] 5.3 Format each condition as `│  Condition<N>: <lhs> <operator> <rhs>` lines
- [x] 5.4 Determine decision result: true if true_branch.id in weights, false if false_branch.id in weights, handle XCASHX fallback
- [x] 5.5 Add `│  Decision: <true|false>` line
- [x] 5.6 Resolve NAV for true_branch and false_branch (asset → price, strategy → nav_array[t_idx])
- [x] 5.7 Add `│   - true: NAV <name> nav= <value>  w=<weight>  id=<id>` and `│   - false: ...` lines, appending `[SELECTED]` to the selected branch
- [x] 5.8 Add NAV node line and `└─` footer, emit as single `logger.debug` call

## 6. Wire formatters into `_upward_pass()`

- [x] 6.1 After NAV computation for each node in `_upward_pass()`, dispatch to the appropriate formatter based on node type (WeightNode → `_log_upward_weight`, FilterNode → `_log_upward_filter`, IfElseNode → `_log_upward_ifelse`)
- [x] 6.2 Remove or retain the existing individual `logger.debug("NAV  node=...")` call — retained for backward compatibility per proposal

## 7. Add UPWARD keyword test

- [x] 7.1 In `tests/unit/test_logging.py`, add `"UPWARD"` to the keyword list in `test_keyword_anchors_in_log`
- [x] 7.2 Add a test `test_upward_pass_detail_at_debug_level` that verifies the `┌─` block appears when logger is at DEBUG and does not appear when logger is at INFO

## 8. Run tests

- [x] 8.1 Run `uv run pytest` and confirm all tests pass

## 9. Refactor: UPWARD pass shows NAVs only; DOWNWARD pass shows decision detail

The UPWARD pass logs currently show weights, selection markers, and decisions that
were set during the *previous* DOWNWARD pass — this is misleading. The UPWARD pass
only computes NAVs; investment decisions are made in the DOWNWARD pass.

- [x] 9.1 Simplify `_log_upward_weight`: remove `w=` from child lines; show only `│  NAV <name>  nav= <value>  id=<id>` for each child
- [x] 9.2 Simplify `_log_upward_filter`: remove `↓`/`✗` markers, `Config:` line, and `[dropped]` labels; show only `│  NAV <name>  nav= <value>  id=<id>` for each child in `node.children`
- [x] 9.3 Simplify `_log_upward_ifelse`: remove conditions, Decision, and [SELECTED]; show only `│  NAV <branch_name>  nav= <value>  id=<id>` for true_branch and false_branch
- [x] 9.4 Add `_log_downward_weight(node, t_idx, runner)` in runner.py: emit `┌─` block with `type=weight-<method>`, each child with computed `w=<weight>`, `└─` footer
- [x] 9.5 Add `_log_downward_filter(node, t_idx, runner)` in runner.py: emit `┌─` block with `type=filter-<mode><count>`, `Config:` line, selected children with `↓` and weight, dropped children with `✗`, `└─` footer
- [x] 9.6 Add `_log_downward_ifelse(node, t_idx, runner)` in runner.py: emit `┌─` block with `type=if_else`, conditions, Decision, true/false branches with [SELECTED], `└─` footer
- [x] 9.7 In `_downward_pass()` (runner.py), after the algo stack runs for each node, dispatch to the appropriate downward formatter based on node type
- [x] 9.8 Add `date_str` threading into `_downward_pass()` if not already present, for use in log output
- [x] 9.9 Update or add tests to verify downward pass blocks appear at DEBUG level
- [x] 9.10 Run `uv run pytest` and confirm all tests pass
