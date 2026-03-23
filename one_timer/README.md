# One-Off Scripts

Quick extraction scripts for common use cases.

## SPY 2018-2025

Extract daily SPY-only allocations from 2018 to 2025.

**Linux/macOS:**
```bash
./run_spy_2018.sh /path/to/pidb_ib.db
```

**PowerShell (Windows):**
```powershell
.\run_spy_2018.ps1 "C:\path\to\pidb_ib.db"
```

Output is written to `one_timer/output/<YYYYMMDD_HHMM>_spy_2018.csv`.

**Note:** Requires at least 200 trading days of price history before 2018-01-02 in the database.
