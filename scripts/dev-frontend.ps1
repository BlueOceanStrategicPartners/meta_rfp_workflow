$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $RepoRoot "frontend")
Write-Host "Vite dev server (HMR) -> http://127.0.0.1:5173" -ForegroundColor Cyan
npm run dev -- --host 127.0.0.1
