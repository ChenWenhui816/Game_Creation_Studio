# Browser-first launcher: starts the local console and opens the default browser.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "Starting Game Creation Studio..." -ForegroundColor Cyan
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 scripts/gameconsole.py serve
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python scripts/gameconsole.py serve
} else {
    throw "Python 3 not found. Install Python 3.10+ first."
}
