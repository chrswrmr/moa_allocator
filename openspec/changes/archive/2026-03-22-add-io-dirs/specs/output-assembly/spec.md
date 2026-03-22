## REMOVED Requirements

### Requirement: CSV output

**Reason**: Write responsibility has moved to the CLI (`main.py`). `Runner.run()` is a pure compute function that returns a `DataFrame` — it SHALL NOT write any files. Embedding I/O in the engine made it impossible to control output naming and destination from the caller, and forced filesystem side-effects on every unit test.

**Migration**: Callers that relied on `Runner.run()` producing `output/allocations.csv` must write the CSV themselves. `main.py` does this via `df.to_csv(output_path, index=False)`. Library callers using `moa_allocations.run()` receive the `DataFrame` directly and may write it as needed.
