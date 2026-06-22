# ApplyPilot setup script — Windows (PowerShell 7+)
# Run from: C:\Users\you\.applypilot\
# Usage: .\install.ps1
$ErrorActionPreference = "Stop"
$ApplyPilotDir = "$env:USERPROFILE\.applypilot"

Write-Host "=== ApplyPilot Setup ===" -ForegroundColor Cyan

# ── 1. uv ────────────────────────────────────────────────────────────────────
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}
Write-Host "✓ uv"

# ── 2. applypilot ────────────────────────────────────────────────────────────
Write-Host "Installing applypilot..."
& uv tool install applypilot
$env:PATH = "$env:USERPROFILE\.local\bin;$env:APPDATA\Python\Scripts;$env:PATH"
Write-Host "✓ applypilot"

# ── 3. patches ───────────────────────────────────────────────────────────────
Write-Host "Applying patches..."
$dst = & python -c "import applypilot, os; print(os.path.dirname(applypilot.__file__))" 2>$null
if (-not $dst) { Write-Error "Cannot find applypilot package. Check uv tool install."; exit 1 }
$src = "$ApplyPilotDir\patches"
@("scoring\validator.py", "scoring\tailor.py", "scoring\pdf.py", "cli.py", "apply\prompt.py") | ForEach-Object {
    Copy-Item -Force (Join-Path $src $_) (Join-Path $dst $_)
}
Write-Host "✓ Patches applied to $dst"

# ── 4. config templates ──────────────────────────────────────────────────────
if (-not (Test-Path "$ApplyPilotDir\.env"))         { Copy-Item "$ApplyPilotDir\.env.example"                 "$ApplyPilotDir\.env" }
if (-not (Test-Path "$ApplyPilotDir\profile.json")) { Copy-Item "$ApplyPilotDir\config\profile.example.json"  "$ApplyPilotDir\profile.json" }
if (-not (Test-Path "$ApplyPilotDir\searches.yaml")){ Copy-Item "$ApplyPilotDir\config\searches.example.yaml" "$ApplyPilotDir\searches.yaml" }
Write-Host "✓ Config templates ready"

# ── 5. Scheduled task (apply daemon every 12h) ───────────────────────────────
$taskName = "ApplyPilot-Apply"
$action   = New-ScheduledTaskAction `
    -Execute "pwsh.exe" `
    -Argument "-NonInteractive -File `"$ApplyPilotDir\apply_daemon.ps1`""
$trigger  = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 12) -Once -At (Get-Date)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -RunLevel Highest -Force | Out-Null
Write-Host "✓ Scheduled task installed (every 12h)"

Write-Host ""
Write-Host "=== Done! Next steps ===================================" -ForegroundColor Green
Write-Host ""
Write-Host "  1. Edit $ApplyPilotDir\.env          - add API keys"
Write-Host "  2. Edit $ApplyPilotDir\profile.json  - fill in personal info"
Write-Host "  3. Add resume: $ApplyPilotDir\resume.txt  (plain text)"
Write-Host "                 $ApplyPilotDir\resume.pdf  (PDF)"
Write-Host "  4. Edit $ApplyPilotDir\searches.yaml - set job queries"
Write-Host "  5. applypilot init"
Write-Host "  6. applypilot run"
Write-Host ""
Write-Host "  Optional: import n8n\applypilot-github-ingestion.json"
Write-Host "            into n8n for automated job discovery."
Write-Host ""
