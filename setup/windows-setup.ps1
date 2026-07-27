<#
    CVSniper - dependency installer for Windows (PowerShell)

    Same job as windows-setup.bat, for anyone who prefers PowerShell or is
    scripting the install. Run it from the project root:

        powershell -ExecutionPolicy Bypass -File setup\windows-setup.ps1
#>

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  CVSniper - setup" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# --- Python -----------------------------------------------------------------
# The py launcher is preferred: on Windows `python` is often the Store stub,
# which opens the Microsoft Store instead of running anything.
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = 'py'; $pyArgs = @('-3') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = 'python'; $pyArgs = @() }

if (-not $py) {
    Write-Host "  ERROR: Python was not found." -ForegroundColor Red
    Write-Host "  Install it from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "  and tick 'Add Python to PATH' during the install." -ForegroundColor Red
    exit 1
}

$version = (& $py @pyArgs --version) 2>&1
Write-Host "  Python found: $version" -ForegroundColor Green

# --- Dependencies ------------------------------------------------------------
Write-Host ""
Write-Host "  Installing dependencies (this takes a couple of minutes)..." -ForegroundColor Yellow
Write-Host ""

& $py @pyArgs -m pip install --upgrade pip --quiet
& $py @pyArgs -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: the dependencies could not be installed." -ForegroundColor Red
    Write-Host "  Check your internet connection and the error above." -ForegroundColor Red
    exit 1
}

# --- Config files ------------------------------------------------------------
# Only the *.default.py templates are versioned. The real config files hold
# personal data and API keys, so they stay out of git and are created here.
Write-Host ""
Write-Host "  Preparing the config files..." -ForegroundColor Yellow
foreach ($f in @('personals', 'questions', 'search', 'settings', 'secrets')) {
    $real = "config\$f.py"
    $tpl = "config\$f.default.py"
    if (Test-Path $real) {
        Write-Host "    $real already exists, left untouched" -ForegroundColor DarkGray
    } elseif (Test-Path $tpl) {
        Copy-Item $tpl $real -Force
        Write-Host "    created $real" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Done. Start the bot with:" -ForegroundColor Green
Write-Host ""
Write-Host "      $py $($pyArgs -join ' ') runAiBot.py" -ForegroundColor White
Write-Host ""
Write-Host "  Everything is configured from the settings" -ForegroundColor Green
Write-Host "  window, no need to edit files by hand." -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
