"""
build_release.py - Genera un paquete limpio de CVSniper sin datos personales.

Uso: python build_release.py
Salida: CVSniper_Release/ (carpeta) + CVSniper_Release.zip

El paquete incluye un instalador que descarga Python 3.12 embebido
automaticamente — el usuario final NO necesita Python instalado.
"""

import os
import shutil
import zipfile
import json
from pathlib import Path

# ── Configuracion ──────────────────────────────────────────────────────────────

ROOT       = Path(__file__).parent
OUTPUT_DIR = ROOT / "CVSniper_Release"
ZIP_NAME   = ROOT / "CVSniper_Release.zip"

PYTHON_VERSION = "3.12.10"   # version embebida a descargar en el instalador

CONFIG_REPLACEMENTS = ["personals", "secrets", "questions", "search", "settings"]

IGNORE = {
    "__pycache__", ".git", ".gitignore",
    "CVSniper_Release", "CVSniper_Release.zip",
    "_release_build", "_release_test_build",
    "build_release.py", "release.ps1", "release_notes.md",
    ".claude", "CVSniper", "REVISED_CV.md", "qa_database.json",
    ".setup_done",
}

CONFIG_IGNORE = {
    "secrets.py", "personals.py", "questions.py",
    "search.py", "settings.py", "resume.py", "user_config.json",
}

CLEAN_USER_CONFIG = {
    "_comment": "CVSniper user configuration. Edit from the web UI at http://127.0.0.1:5000",
    "personals": {}, "questions": {}, "search": {}, "secrets": {}
}

# ── Scripts generados en el release ───────────────────────────────────────────

# Doble-click para instalar todo
SETUP_BAT = r"""@echo off
title CVSniper - Instalador
echo.
echo  ============================================
echo    CVSniper - Instalacion inicial
echo  ============================================
echo.
echo  Este proceso va a:
echo    1. Descargar Python 3.12 (embebido, solo para CVSniper)
echo    2. Instalar las dependencias de Python
echo    3. Descargar ChromeDriver compatible con tu Chrome
echo.
echo  Requiere conexion a internet. Puede tardar 3-5 minutos.
echo.
pause

powershell -ExecutionPolicy Bypass -File "%~dp0SETUP.ps1"
pause
"""

# Script PowerShell que hace el trabajo real
SETUP_PS1 = f"""# SETUP.ps1 - Instala CVSniper usando un entorno virtual de Python
# Si Python ya esta instalado en el sistema, lo usa directamente.
# Si no, descarga e instala Python 3.12 automaticamente.

$ErrorActionPreference = "Stop"
$Root    = $PSScriptRoot
$VenvDir = "$Root\\venv"
$PyExe   = "$VenvDir\\Scripts\\python.exe"

function Write-Step($n, $msg) {{
    Write-Host ""
    Write-Host "[$n/3] $msg" -ForegroundColor Cyan
}}

# Busca cualquier Python 3.10+ en el sistema
function Find-SystemPython {{
    # py launcher — prueba versiones modernas
    foreach ($v in @("3.13", "3.12", "3.11", "3.10")) {{
        try {{
            $p = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($p -and (Test-Path $p)) {{ return $p }}
        }} catch {{}}
    }}
    # Comando python en PATH
    try {{
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) {{
            $ver = & python -c "import sys; v=sys.version_info; print(v.major*100+v.minor)" 2>$null
            if ([int]$ver -ge 310) {{ return $cmd.Source }}
        }}
    }} catch {{}}
    # Ubicaciones tipicas de instalacion
    foreach ($v in @("313","312","311","310")) {{
        foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles)) {{
            $p = "$base\\Programs\\Python\\Python$v\\python.exe"
            if (Test-Path $p) {{ return $p }}
        }}
    }}
    return $null
}}

# ── Paso 1: Entorno virtual ────────────────────────────────────────────────────
Write-Step 1 "Configurando entorno de Python..."

if (Test-Path $PyExe) {{
    Write-Host "  Entorno virtual ya existe, saltando." -ForegroundColor Green
}} else {{
    $SysPy = Find-SystemPython

    if (-not $SysPy) {{
        Write-Host "  Python no encontrado. Descargando Python 3.12..." -ForegroundColor Yellow
        $installer = "$Root\\python_setup.exe"
        $url = "https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"
        try {{
            Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
        }} catch {{
            Write-Host "[ERROR] No se pudo descargar Python. Verifica tu internet." -ForegroundColor Red
            exit 1
        }}
        Write-Host "  Instalando Python 3.12 (puede tardar un minuto)..."
        $proc = Start-Process -FilePath $installer `
            -ArgumentList "/quiet InstallAllUsers=0 Include_tcltk=1 Include_pip=1 Include_test=0 Include_doc=0 PrependPath=0 Shortcuts=0" `
            -Wait -PassThru
        Remove-Item $installer -ErrorAction SilentlyContinue
        $SysPy = Find-SystemPython
    }}

    if (-not $SysPy) {{
        Write-Host ""
        Write-Host "[ERROR] Python no encontrado. Instala Python 3.10 o superior desde:" -ForegroundColor Red
        Write-Host "  https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "Luego vuelve a correr SETUP.bat." -ForegroundColor Yellow
        pause
        exit 1
    }}

    Write-Host "  Python del sistema: $SysPy" -ForegroundColor Green
    Write-Host "  Creando entorno virtual (tkinter incluido automaticamente)..."
    & $SysPy -m venv "$VenvDir"
    if (-not (Test-Path $PyExe)) {{
        Write-Host "[ERROR] No se pudo crear el entorno virtual." -ForegroundColor Red
        exit 1
    }}
    Write-Host "  Entorno virtual listo." -ForegroundColor Green
}}

# ── Paso 2: Dependencias ───────────────────────────────────────────────────────
Write-Step 2 "Instalando dependencias..."

$maxRetries = 3
$attempt    = 0
$success    = $false

while (-not $success -and $attempt -lt $maxRetries) {{
    $attempt++
    if ($attempt -gt 1) {{
        Write-Host "  Reintentando ($attempt/$maxRetries)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }}
    & $PyExe -m pip install -r "$Root\\requirements.txt" `
        --no-warn-script-location `
        --retries 5 `
        --timeout 60 `
        --quiet
    if ($LASTEXITCODE -eq 0) {{ $success = $true }}
}}

if (-not $success) {{
    Write-Host ""
    Write-Host "[ERROR] Fallo la instalacion de dependencias." -ForegroundColor Red
    Write-Host "Verifica tu internet y vuelve a correr SETUP.bat." -ForegroundColor Yellow
    exit 1
}}
Write-Host "  Dependencias instaladas." -ForegroundColor Green

# ── Paso 3: ChromeDriver ───────────────────────────────────────────────────────
Write-Step 3 "Configurando ChromeDriver..."

$ChromeDir = "$Root\\chrome_driver"
$ChromeExe = "$ChromeDir\\chromedriver.exe"

if (Test-Path $ChromeExe) {{
    Write-Host "  ChromeDriver ya instalado, saltando." -ForegroundColor Green
}} else {{
    New-Item -ItemType Directory -Force -Path $ChromeDir | Out-Null
    try {{
        $versionsUrl = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json"
        $versionsJson = Invoke-WebRequest -Uri $versionsUrl -UseBasicParsing | ConvertFrom-Json
        $cdVersion = $versionsJson.channels.Stable.version
        $cdUrl = "https://storage.googleapis.com/chrome-for-testing-public/$cdVersion/win64/chromedriver-win64.zip"
        $cdZip = "$Root\\chromedriver.zip"
        Write-Host "  Descargando ChromeDriver $cdVersion..."
        Invoke-WebRequest -Uri $cdUrl -OutFile $cdZip -UseBasicParsing
        Expand-Archive -Path $cdZip -DestinationPath $ChromeDir -Force
        Remove-Item $cdZip -ErrorAction SilentlyContinue
        $innerExe = Get-ChildItem $ChromeDir -Recurse -Filter "chromedriver.exe" | Select-Object -First 1
        if ($innerExe -and $innerExe.FullName -ne $ChromeExe) {{
            Move-Item $innerExe.FullName $ChromeExe -Force
        }}
        Write-Host "  ChromeDriver instalado." -ForegroundColor Green
    }} catch {{
        Write-Host "  [AVISO] ChromeDriver se descargara automaticamente al primer inicio." -ForegroundColor Yellow
    }}
}}

# ── Crear START_CVSniper.bat con la ruta absoluta al venv ─────────────────────
$startContent  = "@echo off`r`n"
$startContent += "title CVSniper`r`n"
$startContent += "cd /d `"$Root`"`r`n"
$startContent += "set PYTHONPATH=$Root`r`n"
$startContent += "`"$PyExe`" `"$Root\\runAiBot.py`"`r`n"
$startContent += "pause`r`n"
[System.IO.File]::WriteAllText("$Root\\START_CVSniper.bat", $startContent, [System.Text.Encoding]::ASCII)

# ── Verificacion final ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[Verificando instalacion...]" -ForegroundColor Cyan
$criticalModules = @("tkinter", "flask", "selenium", "pyautogui", "openai")
$failed = @()
foreach ($mod in $criticalModules) {{
    & $PyExe -c "import $mod" 2>$null
    if ($LASTEXITCODE -ne 0) {{
        $failed += $mod
        Write-Host "  [FALLO] $mod" -ForegroundColor Red
    }} else {{
        Write-Host "  [OK] $mod" -ForegroundColor Green
    }}
}}

if ($failed.Count -gt 0) {{
    Write-Host ""
    Write-Host "[ERROR] Modulos faltantes: $($failed -join ', ')" -ForegroundColor Red
    Write-Host "Borra la carpeta venv/ y vuelve a correr SETUP.bat." -ForegroundColor Yellow
    exit 1
}}

# Marcar setup como completo
"OK" | Set-Content "$Root\\.setup_done" -Encoding ascii

# ── Resultado ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host " ============================================" -ForegroundColor Green
Write-Host "   INSTALACION COMPLETA" -ForegroundColor Green
Write-Host " ============================================" -ForegroundColor Green
Write-Host ""
Write-Host " Ahora puedes iniciar CVSniper:" -ForegroundColor White
Write-Host "   Doble click en START_CVSniper.bat" -ForegroundColor Cyan
Write-Host ""
"""

# Placeholder inicial — SETUP.ps1 lo sobreescribe con rutas absolutas al venv
START_BAT = r"""@echo off
title CVSniper
cd /d "%~dp0"

if not exist ".setup_done" (
    echo.
    echo [AVISO] El setup no se ha completado todavia.
    echo Corre SETUP.bat primero y espera que termine.
    echo.
    pause
    exit /b 1
)

set PYTHONPATH=%~dp0

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe runAiBot.py
) else (
    echo.
    echo [ERROR] Entorno virtual no encontrado. Corre SETUP.bat primero.
    echo.
    pause
    exit /b 1
)
pause
"""

LEEME = f"""\
# CVSniper - Inicio Rapido

## Requisitos
- Windows 10 o Windows 11
- Google Chrome instalado

No necesitas instalar Python. El instalador lo incluye automaticamente.

## Pasos

1. Doble click en SETUP.bat
   - Descarga Python {PYTHON_VERSION} (solo para CVSniper, no afecta tu sistema)
   - Instala las dependencias
   - Instala ChromeDriver compatible con tu Chrome
   - Crea START_CVSniper.bat listo para usar

2. Doble click en START_CVSniper.bat para iniciar el bot

3. Se abre una ventana de control y el panel web en http://127.0.0.1:5000
   - Completa tu informacion en el panel
   - El bot empieza automaticamente cuando guardas

## IA gratuita recomendada
Usa Groq: crea cuenta en https://console.groq.com
Genera una API Key y pegala en el panel web (seccion Credenciales / IA).

## Soporte
GitHub: https://github.com/Disaqx/CVSniper
"""


# ── Funciones de copia ─────────────────────────────────────────────────────────

def should_ignore(path: Path) -> bool:
    return path.name in IGNORE or path.name.startswith(".")


def copy_tree(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if should_ignore(item):
            continue
        dest_item = dst / item.name
        if item.is_dir():
            if item.name == "config":
                copy_config(item, dest_item)
            elif item.name in {"all resumes", "all excels", "logs"}:
                dest_item.mkdir(parents=True, exist_ok=True)
                (dest_item / ".gitkeep").write_text("")
            else:
                copy_tree(item, dest_item)
        elif item.is_file():
            shutil.copy2(item, dest_item)


def copy_config(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in CONFIG_IGNORE or item.is_dir():
            continue
        shutil.copy2(item, dst / item.name)

    for cfg_name in CONFIG_REPLACEMENTS:
        default_file = src / f"{cfg_name}.default.py"
        if default_file.exists():
            shutil.copy2(default_file, dst / f"{cfg_name}.py")
            print(f"  [config] {cfg_name}.py <- template limpio")

    (dst / "user_config.json").write_text(
        json.dumps(CLEAN_USER_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("  [config] user_config.json <- vacio")

    resume_src = src / "resume.py"
    if resume_src.exists():
        shutil.copy2(resume_src, dst / "resume.py")


def create_installer_scripts(dst: Path):
    (dst / "SETUP.bat").write_text(SETUP_BAT, encoding="utf-8")
    (dst / "SETUP.ps1").write_text(SETUP_PS1, encoding="utf-8")
    (dst / "START_CVSniper.bat").write_text(START_BAT, encoding="utf-8")
    (dst / "LEEME_QuickStart.md").write_text(LEEME, encoding="utf-8")
    print("  [scripts] SETUP.bat, SETUP.ps1, START_CVSniper.bat, LEEME creados")


def zip_release(src: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob("*"):
            zf.write(file, file.relative_to(src.parent))
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\n[ZIP] {zip_path.name} ({size_mb:.1f} MB)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  CVSniper - Build Release")
    print("=" * 55)

    if OUTPUT_DIR.exists():
        print(f"\nEliminando release anterior...")
        shutil.rmtree(OUTPUT_DIR)
    if ZIP_NAME.exists():
        ZIP_NAME.unlink()

    print(f"\nCopiando archivos...")
    copy_tree(ROOT, OUTPUT_DIR)

    print("\nCreando scripts del instalador...")
    create_installer_scripts(OUTPUT_DIR)

    print("\nComprimiendo...")
    zip_release(OUTPUT_DIR, ZIP_NAME)

    print("\n" + "=" * 55)
    print("  BUILD COMPLETO")
    print("=" * 55)
    print(f"  ZIP: {ZIP_NAME.name}")
    print("\nEl usuario solo necesita:")
    print("  1. Descomprimir el ZIP")
    print("  2. Doble click en SETUP.bat")
    print("  3. Doble click en START_CVSniper.bat")


if __name__ == "__main__":
    main()
