## Context

The compiler produces a `RootNode` and the engine's `Runner` consumes it alongside a `pd.DataFrame` of price data to produce daily allocations. Today these are disconnected — there is no code that fetches price data or wires the two together. The `run()` function fills this gap as the package's only public entry point.

Price data comes from `pidb_ib`, an external package providing `PidbReader.get_matrix()`. This returns a **Polars** DataFrame in wide format with a string `date` column. The engine expects a **pandas** DataFrame with a `DatetimeIndex`. The conversion must happen in `run()`.

A sequencing challenge exists: `run()` must know the required tickers and max lookback *before* fetching prices, but `_collect_tickers()` and `_compute_max_lookback()` are currently private functions inside `runner.py`, called during `Runner.__init__()`.

## Goals / Non-Goals

**Goals:**
- Single function `run(strategy_path, price_fetcher?) -> pd.DataFrame` that executes the full pipeline
- Correct lookback-adjusted date window so the engine's price_data contract is satisfied
- Pluggable price fetching: default uses pidb_ib, but callers can inject any function matching the `PriceFetcher` contract to test alternative data sources (e.g. different close price columns)
- `pidb_ib` is imported only in the default fetcher — the engine and compiler never know about it

**Non-Goals:**
- Caching or reusing `PidbReader` instances across calls
- Exposing intermediate results (compiled tree, raw prices) to callers
- `bt_rebalancer` or `iba` integration
- Handling multiple strategies in a single call
- Any changes to `Runner`, compiler, or algo behavior

## Decisions

### D1: Expose `_collect_tickers` and `_compute_max_lookback` as public functions

`run()` needs tickers and max lookback to compute the fetch window *before* constructing `Runner`. These are currently private (`_`-prefixed) in `runner.py`.

**Decision:** Rename to `collect_tickers()` and `compute_max_lookback()` (drop the underscore) and export them from `moa_allocations.engine`. They are pure tree-inspection utilities with no dependency on `Runner` state. `Runner.__init__()` continues to call them internally — no duplication.

**Alternatives considered:**
- *Duplicate the logic in `run()`* — violates DRY; the BFS walks are non-trivial and would diverge over time.
- *Pass a price-fetcher callback to Runner* — over-engineered; changes Runner's interface for no benefit to the engine itself.
- *Two-phase Runner (construct, then inject prices)* — breaks Runner's current "validate everything on init" contract and adds complexity.

### D2: Pluggable `price_fetcher` with pidb_ib as default

`run()` accepts an optional `price_fetcher` callable. This decouples the orchestration from the data source, allowing callers to swap in alternative fetchers (e.g. to A/B test different close price columns from pidb_ib, or use an entirely different data source).

**Contract:** `PriceFetcher = Callable[[list[str], str, str], pd.DataFrame]`
- Args: `(tickers, start_date, end_date)` — tickers as uppercase strings, dates as ISO strings
- Returns: `pd.DataFrame` matching the engine's price_data contract (DatetimeIndex, uppercase ticker columns, float64 values, no NaNs)

**Default fetcher:** A private `_default_price_fetcher()` function that wraps `PidbReader.get_matrix()`. It reads `PIDB_IB_DB_PATH` from the environment, calls `get_matrix()`, and runs the Polars-to-pandas conversion. All pidb_ib knowledge is confined to this one function.

**Alternatives considered:**
- *Hard-code pidb_ib in `run()` with no injection point* — works today but forces callers to fork `run()` to test alternative data. Costs almost nothing to add the parameter now.
- *Abstract base class / protocol for data sources* — over-engineered for a single function signature; a callable is sufficient.
- *Adapter module (`moa_allocations/data.py`)* — adds a file and import path for what is effectively one function. The callable parameter is lighter.

### D3: Polars-to-pandas conversion inside the default fetcher

The conversion from `PidbReader.get_matrix()` output to the engine's price_data contract involves:
1. Convert Polars `date` string column → pandas `DatetimeIndex`
2. Drop the `date` column, set index
3. Ensure column names are uppercase ticker strings
4. Ensure values are `float64`

**Decision:** This conversion lives inside `_default_price_fetcher()`, not in `run()`. Custom fetchers are responsible for returning a pandas DataFrame that already matches the contract. This keeps the conversion logic co-located with the pidb_ib call — if you replace the data source, you don't inherit pidb_ib's format assumptions.

### D4: Trading-day lookback → calendar-date conversion

The engine spec requires price data covering `[start_date - max_lookback_days, end_date]`. `compute_max_lookback()` returns an `int` counting **trading days** (as all DSL lookback values do). `get_matrix(start=...)` accepts a **calendar date**.

To convert: multiply trading days by `7/5` (5 trading days per 7 calendar days) and add a fixed buffer for holidays (~10 days/year). This guarantees we always overshoot the required window.

**Decision:** Compute `calendar_days = ceil(max_lookback * 7 / 5) + 10`, then `fetch_start = settings.start_date - timedelta(days=calendar_days)`. The overshoot is intentional — extra rows before the window are harmless (Runner ignores them), while too few rows would cause `PriceDataError`.

### D5: Error propagation — no wrapping

**Decision:** Let exceptions from `compile_strategy()` (`DSLValidationError`), `Runner` (`PriceDataError`), and the price fetcher propagate directly. `run()` raises no new exceptions of its own. The default fetcher raises `ValueError` when `PIDB_IB_DB_PATH` is unset. No custom wrapper exception — callers can catch specific errors from each layer.

## Risks / Trade-offs

- **[pidb_ib availability]** `pidb_ib` must be on `PYTHONPATH` at runtime when using the default fetcher. If it's missing, import fails with `ImportError`. → *Mitigation:* This is expected for the default path. Custom fetchers can avoid the dependency entirely.

- **[Polars version coupling]** The default fetcher assumes `PidbReader.get_matrix()` returns a Polars DataFrame with a `date` string column. If pidb_ib changes its return format, the default fetcher breaks. → *Mitigation:* pidb_ib's API is documented and stable. The coupling is confined to one function — custom fetchers are unaffected.

- **[Lookback calendar conversion is approximate]** The `7/5 + 10` conversion from trading days to calendar days is a heuristic. Markets with unusual holiday schedules could theoretically exhaust the buffer. → *Mitigation:* The +10 day buffer covers well beyond typical US/EU holiday density (~8-10 holidays/year). If `Runner` raises `PriceDataError` due to insufficient data, the fix is to increase the buffer — a clear, local change. Overshooting is always safe (extra rows are ignored by Runner).
