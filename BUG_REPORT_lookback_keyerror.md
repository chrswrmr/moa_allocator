# Bug: KeyError 'lookback' in moa_allocations on valid strategy

## Summary
`moa_allocations` exits with code 3 and message `'lookback'` (KeyError) when running a backtest on a strategy that uses `sma_price` with a `lookback` field inside an `if_else` condition under a `weight: inverse_volatility` root.

## Environment
- moa_allocator path: `c:\py\moa_allocator`
- Called via: `uv run python -m moa_allocations --json --output <temp_dir> --strategy <strat_path>`
- Date observed: 2026-04-09

## Reproduction

Strategy DSL (`speed test.moastrat.json`):

```json
{
  "version-dsl": "1.0.0",
  "settings": {
    "starting_cash": 100000,
    "start_date": "2020-01-01",
    "end_date": "2025-12-01",
    "rebalance_frequency": "monthly",
    "fees": 0,
    "slippage": 0.0005
  },
  "root_node": {
    "type": "weight",
    "method": "inverse_volatility",
    "children": [
      { "type": "asset", "ticker": "DBC" },
      {
        "type": "if_else",
        "logic_mode": "all",
        "conditions": [
          {
            "lhs": { "asset": "SPY", "function": "sma_price", "lookback": "20d" },
            "comparator": "greater_than",
            "rhs": { "asset": "SPY", "function": "sma_price", "lookback": "200d" },
            "duration": "1d"
          }
        ],
        "true_branch": { "type": "asset", "ticker": "TQQQ" },
        "false_branch": {
          "type": "filter",
          "sort_by": { "function": "cumulative_return", "lookback": "20d" },
          "select": { "mode": "top", "count": 2 },
          "children": [
            { "type": "asset", "ticker": "GLD" },
            { "type": "asset", "ticker": "AGG" },
            { "type": "asset", "ticker": "FLOT" },
            { "type": "asset", "ticker": "CORP" },
            { "type": "asset", "ticker": "HYG" }
          ]
        }
      },
      { "type": "asset", "ticker": "XLF" },
      { "type": "asset", "ticker": "XLK" },
      { "type": "asset", "ticker": "XLP" }
    ]
  }
}
```

Run:
```
uv run python -m moa_allocations --json --output /tmp/out --strategy "speed test.moastrat.json"
```

## Expected
JSON output with `status: "ok"` and `allocations_path` to a CSV.

## Actual
Exit code 3, JSON output:
```json
{ "status": "error", "code": 3, "message": "'lookback'" }
```

A `KeyError: 'lookback'` is being raised somewhere in the strategy parser/evaluator.

## Validation passes
The same strategy passes `--validate` cleanly. Only `--strategy` (full run) crashes. This means schema validation accepts the structure but the runtime evaluator chokes on it.

## Notes
- Validation succeeded — this is not a DSL schema issue, it's a runtime KeyError
- Possible suspects: condition evaluator, `sma_price` indicator handler, or filter `sort_by` parser
- See related work: `openspec/changes/daily-only-lookback/` — recent changes to lookback parsing may be related
- Inputs are preserved at the temp paths logged by moa_shell on failure for debugging

## Impact
Blocks backtest execution from moa_shell for any strategy combining `if_else` conditions with `sma_price` indicators under a `weight: inverse_volatility` root. Multiple distinct strategies hit this error consistently.
