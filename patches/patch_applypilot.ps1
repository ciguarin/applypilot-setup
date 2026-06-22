# ApplyPilot patch script for Windows
# Run from PowerShell after: uv tool upgrade applypilot
# & "$env:USERPROFILE\.applypilot\patches\patch_applypilot.ps1"

$ErrorActionPreference = "Stop"

$dst = & python -c "import applypilot, os; print(os.path.dirname(applypilot.__file__))" 2>$null
if (-not $dst) {
    Write-Error "Could not locate applypilot package. Is it installed and on PATH?"
    exit 1
}

$src = "$env:USERPROFILE\.applypilot\patches"

Write-Host "Patching: $dst"

@(
    "scoring\validator.py",
    "scoring\tailor.py",
    "scoring\pdf.py",
    "cli.py",
    "apply\prompt.py"
) | ForEach-Object {
    Copy-Item -Force (Join-Path $src $_) (Join-Path $dst $_)
    Write-Host "Patched: $_"
}

Write-Host "`nAll patches applied to $dst"
