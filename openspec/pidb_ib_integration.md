# pidb_ib Integration Reference

For standard approach to accessing `pidb_ib` price data from `moa_rebalancer` or other downstream packages, see:

**👉 [`../../pidb_ib/PIDB_ACCESS_GUIDE.md`](../../pidb_ib/PIDB_ACCESS_GUIDE.md)**

This guide covers:
- Setup (editable dependency in `pyproject.toml`)
- `PidbReader` API contract
- Configuration (database paths, dates, symbols)
- Error handling patterns
- Best practices (exclude `XCASHX`, validate symbols, handle NaN)
- Quick reference examples

**Current implementation in moa_rebalancer:**
- Location: `moa_rebalancer/parser.py:get_prices()`
- Imports: `from access import PidbReader`
- Returns: `pd.DataFrame` with `DatetimeIndex`, columns `{SYMBOL}_close_d`

Use this guide as reference when implementing `moa_allocator` or other packages that need pidb_ib price data.
