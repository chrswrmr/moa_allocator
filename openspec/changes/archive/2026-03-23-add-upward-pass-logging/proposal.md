# Proposal: Add UPWARD Pass Logging

## Why

The current log output provides visibility into NAV values during the upward pass, but lacks structured context about **which children feed into each node** and **the flow of the pass itself**. Users cannot easily trace data dependencies or understand which assets/branches contribute to intermediate node values. Adding detailed, structured pass logging makes the upward pass transparent and debuggable.

## What Changes

- Add `UPWARD start` and `UPWARD complete` log entries to demarcate the upward pass boundaries
- For each node processed in the upward pass, log:
  - Node name, type, and ID
  - Direct children (asset tickers and strategy node names) with their NAV values and weights
  - Final calculated NAV for the node
- Implement per-node-type formatting patterns:
  - **WeightNode**: show child selection and weight allocation method (equal, defined, inverse_volatility)
  - **FilterNode**: show metric and lookback config, mark selected vs. dropped children
  - **IfElseNode**: show conditions, decision result, and both branch options with [SELECTED] marker

## Capabilities

### New Capabilities
- `upward-pass-logging`: Structured, hierarchical logging of the upward pass execution with per-node-type formatting and child-to-parent data flow visibility

### Modified Capabilities
(none — this is a pure observability enhancement; no spec-level behavior changes)

## Impact

- **Modified**: `moa_allocations/engine/runner.py` — enhance `_upward_pass()` method to add structured logging; add helper functions for per-node-type formatting
- **Dependencies**: Uses existing `logger` (initialized in module); respects existing log level configuration
- **Backward compatibility**: Fully backward compatible; existing NAV logs unchanged, only adds new structured pass-level entries

## Notes

Log output should follow the design patterns finalized in explore mode:
- Box-drawing characters (`┌─`, `│`, `└─`) for visual hierarchy
- Child entries marked with `←` for inputs
- `↓` and `✗` symbols in FilterNode for selected/dropped
- Text-based branch labels in IfElseNode (no symbols)
- All IDs placed at end of row
