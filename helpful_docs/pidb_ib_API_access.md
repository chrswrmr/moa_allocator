## 4. Programmatic Data Access (API) for pidb_ib

If you are building external tools (like `moa_allocator`) that need to consume data from `pidb_ib` for backtesting, use the `PidbReader` class. This API is optimized for speed and provides a clean, vectorized interface.

### 4.1 Integration & Usage

You can integrate `PidbReader` by ensuring `pidb_ib` is in your `PYTHONPATH`. Usage is optimized for vectorized bulk requests:

```python
from src.access import PidbReader

# Initialize with the path to your database
reader = PidbReader("data/pidb_ib.db")

# 1. Simple fetch (Single symbol, default metric)
df = reader.get_matrix("SPY")

# 2. Multi-ticker & Multi-metric (Wide Matrix)
df = reader.get_matrix(
    symbols=["SPY", "IWM"],
    columns=["close_d", "close_15minbc"],
    start="2024-01-01", # Optional
    end="2024-12-31"    # Optional
)
# Returns columns: [date, SPY_close_d, SPY_close_15minbc, IWM_close_d, IWM_close_15minbc]
```

### 4.2 Return Format Specification

The `get_matrix` method returns a **Polars DataFrame** in a wide format optimized for vectorization:

- **Rows**: Sorted chronologically by the `date` column (String/UTF-8 format).
- **Columns**:
    - **Single Metric**: If only one column is requested, columns are named directly after the symbols (e.g., `SPY`, `IWM`).
    - **Multi-Metric**: If multiple columns are requested, columns use the `SYMBOL_METRIC` pattern (e.g., `SPY_close_d`, `SPY_close_15minbc`).
- **Values**: 64-bit floats representing the price or metric value. Missing data is represented as `null`.

### 4.3 Why use `get_matrix`?

1.  **Speed**: It uses a single vectorized SQL query and Polars' internal Rust-based pivoting, which is significantly faster than looping over symbols in Python.
2.  **Alignment**: It automatically aligns all symbols onto the same date axis, handling missing days with `null` values.
3.  **Abstraction**: You don't need to know the underlying table name or raw column names.