# Extract SPY-only allocations from 2018-2025
# Usage: .\run_spy_2018.ps1 C:\path\to\pidb_ib.db

param(
    [Parameter(Mandatory=$true)]
    [string]$PidbPath
)

$env:PIDB_IB_DB_PATH = $PidbPath
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projDir = Split-Path -Parent $scriptDir

Set-Location $projDir
uv run python main.py --strategy one_timer/spy_2018.moastrat.json --output one_timer/output
