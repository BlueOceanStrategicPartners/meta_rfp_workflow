# Django dev server with StatReloader (Daphne ASGI). Never use --noreload in local dev.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $RepoRoot "backend"
Set-Location $Backend

$env:DJANGO_SETTINGS_MODULE = "config.settings.local_sqlite"
if (-not $env:CELERY_TASK_ALWAYS_EAGER) {
    $env:CELERY_TASK_ALWAYS_EAGER = "true"
}

$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $pair = $_ -split '=', 2
        if ($pair.Count -eq 2) {
            Set-Item -Path "Env:$($pair[0].Trim())" -Value $pair[1].Trim()
        }
    }
}

Write-Host "Django dev server (autoreload ON) -> http://127.0.0.1:8000" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
