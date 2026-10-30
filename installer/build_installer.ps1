<#
    Builds dist\CVSniper-Setup-<version>.exe, the Windows installer.

        powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1

    Needs, on the machine that BUILDS it (the user who installs needs nothing):
      - Inno Setup 6   https://jrsoftware.org/isdl.php  (or: winget install JRSoftware.InnoSetup)
      - Python 3.12 x64 with Tkinter (the python.org installer includes it)
      - git

    Steps: export the committed app with `git archive` (so personal config
    files, CSVs and logs can never end up inside the installer), copy the
    Python install into build\python, install requirements.txt into that copy,
    check it can import everything, then compile installer\CVSniper.iss.

    Uncommitted changes are NOT included - commit first.
#>
param(
    [string]$Version = "1.0.0",
    # python.exe to bundle. Default: Python 3.12 from the py launcher.
    [string]$PythonExe = ""
)

$ErrorActionPreference = 'Stop'
$Root  = Split-Path $PSScriptRoot -Parent
$Build = Join-Path $Root 'build'
$Dist  = Join-Path $Root 'dist'
Set-Location $Root

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }

# --- Tools -------------------------------------------------------------------
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($p in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                     "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                     "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}
if (-not $iscc) { throw "Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php" }

if (-not $PythonExe) {
    $PythonExe = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
}
$pyHome = (& $PythonExe -c "import sys; print(sys.base_prefix)").Trim()
$pyVer  = (& $PythonExe -c "import sys, platform; print(sys.version.split()[0], platform.architecture()[0])").Trim()
Write-Host "Python to bundle: $pyHome ($pyVer)"
if ($pyVer -notmatch '64bit') { throw "A 64-bit Python is required." }

# --- Clean -------------------------------------------------------------------
Step "Cleaning build\"
if (Test-Path $Build) { Remove-Item $Build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Build, $Dist | Out-Null

# --- App files ---------------------------------------------------------------
Step "Exporting the committed app (git archive HEAD)"
$zip = Join-Path $Build 'app.zip'
git archive --format=zip -o $zip HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Expand-Archive $zip -DestinationPath (Join-Path $Build 'app')
Remove-Item $zip

# --- Private Python ----------------------------------------------------------
# A regular Windows CPython install is relocatable. Its own site-packages and
# Scripts are left out (Scripts holds .exe shims with absolute paths) and pip
# is reinstalled into the copy with ensurepip.
Step "Copying Python from $pyHome"
$py = Join-Path $Build 'python'
New-Item -ItemType Directory -Force -Path $py | Out-Null
Get-ChildItem $pyHome -Force | Where-Object { $_.Name -notin @('Scripts', 'Doc', 'include', 'libs', 'Tools') } |
    ForEach-Object { Copy-Item $_.FullName -Destination $py -Recurse -Force }
$sp = Join-Path $py 'Lib\site-packages'
if (Test-Path $sp) { Remove-Item $sp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $sp | Out-Null
foreach ($junk in @('Lib\test', 'Lib\idlelib\idle_test', 'Lib\tkinter\test')) {
    $p = Join-Path $py $junk
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
$pyExeBuilt = Join-Path $py 'python.exe'

Step "Installing requirements.txt into the bundled Python"
& $pyExeBuilt -E -s -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "ensurepip failed" }
& $pyExeBuilt -E -s -m pip install --no-warn-script-location --disable-pip-version-check -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
$scripts = Join-Path $py 'Scripts'
if (Test-Path $scripts) { Remove-Item $scripts -Recurse -Force }

Step "Checking the bundled Python can run the bot"
& $pyExeBuilt -E -s -c @"
import tkinter; tkinter.Tcl().eval('info patchlevel')
import selenium, flask, flask_cors, pyautogui, undetected_chromedriver, openai, fitz, fpdf, PIL
import google.generativeai
print('bundled Python OK')
"@
if ($LASTEXITCODE -ne 0) { throw "The bundled Python is missing something (see above)." }

# --- Compile -----------------------------------------------------------------
Step "Compiling the installer ($iscc)"
& $iscc "/DAppVersion=$Version" "/DAppDir=$(Join-Path $Build 'app')" "/DPythonDir=$py" (Join-Path $PSScriptRoot 'CVSniper.iss')
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }

$out = Join-Path $Dist "CVSniper-Setup-$Version.exe"
Write-Host ""
Write-Host "Installer ready: $out ($([math]::Round((Get-Item $out).Length / 1MB)) MB)" -ForegroundColor Green
