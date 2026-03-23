#!/bin/bash
# Extract SPY-only allocations from 2018-2025
# Usage: ./run_spy_2018.sh /path/to/pidb_ib.db

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/pidb_ib.db"
    exit 1
fi

export PIDB_IB_DB_PATH="$1"
cd "$(dirname "$0")/.."
uv run python main.py --strategy one_timer/spy_2018.moastrat.json --output one_timer/output
