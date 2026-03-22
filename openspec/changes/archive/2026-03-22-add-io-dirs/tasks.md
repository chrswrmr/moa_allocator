## 1. Engine — remove CSV write from Runner.run()

- [x] 1.1 Delete the `output/allocations.csv` write logic from `Runner.run()` in `moa_allocations/engine/runner.py`
- [x] 1.2 Confirm `Runner.run()` returns the allocations `DataFrame` and exits without touching the filesystem

## 2. Directories

- [x] 2.1 Create `strategies/` at project root with a `.gitkeep` file
- [x] 2.2 Confirm `output/` already exists (no action needed if present); add `.gitkeep` if empty

## 3. CLI entry point — main.py

- [x] 3.1 Replace the stub in `main.py` with an `argparse` parser accepting `--strategy` (required) and `--output` (optional, default `output/`)
- [x] 3.2 In `main()`, call `compile_strategy(args.strategy)` to obtain `root`
- [x] 3.3 Extract tickers and max lookback, compute `fetch_start`, call the default price fetcher (reuse logic from `moa_allocations/__init__.py`)
- [x] 3.4 Construct `Runner(root, price_data)`, call `runner.run()` to obtain the allocations DataFrame
- [x] 3.5 Build the output filename: `YYYYMMDD_HHMM_<stem>.csv` using `datetime.now()` and `Path(args.strategy).stem`
- [x] 3.6 Create the output directory if absent (`Path(args.output).mkdir(parents=True, exist_ok=True)`)
- [x] 3.7 Write the DataFrame to the output path with `df.to_csv(output_path, index=False)`

## 4. Documentation

- [x] 4.1 Add a **Usage** section to `README.md` covering: how to add a strategy to `strategies/`, how to set `PIDB_IB_DB_PATH`, and how to run `uv run python main.py --strategy <path>` to produce output in `output/`

## 5. Tests & verification

- [x] 5.1 Run `uv run pytest` — confirm all existing tests pass (no regressions from removing the CSV write)
