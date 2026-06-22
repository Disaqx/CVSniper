"""
build_release.py - Genera un paquete limpio de CVSniper sin datos personales.

Uso: python build_release.py
Salida: CVSniper_Release/ (carpeta) + CVSniper_Release.zip
"""

import os
import shutil
import zipfile
import json
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "CVSniper_Release"
ZIP_NAME = ROOT / "CVSniper_Release.zip"

# Archivos de config que se reemplazan con la plantilla vacía
CONFIG_REPLACEMENTS = [
    "personals",
    "secrets",
    "questions",
    "search",
    "settings",
]

# Carpetas/archivos a ignorar completamente
IGNORE = {
    "__pycache__",
    ".git",
    ".gitignore",
    "CVSniper_Release",
    "CVSniper_Release.zip",
    "build_release.py",
    ".claude",
    "CVSniper",           # carpeta de build anterior si existe
    "REVISED_CV.md",
    "qa_database.json",
}

# Archivos individuales a ignorar dentro de config/
CONFIG_IGNORE = {
    "secrets.py",
    "personals.py",
    "questions.py",
    "search.py",
    "settings.py",
    "resume.py",
    "user_config.json",
}

# ── user_config.json limpio (sin datos personales) ────────────────────────────

CLEAN_USER_CONFIG = {
    "_comment": "CVSniper user configuration. Edit from the web UI at http://127.0.0.1:5000",
    "personals": {},
    "questions": {},
    "search": {},
    "secrets": {}
}

# ── Contenido de los scripts de ayuda ─────────────────────────────────────────

INSTALL_BAT = r"""@echo off
echo ============================================
echo   CVSniper - Instalacion de dependencias
echo ============================================
echo.

:: Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Por favor instala Python 3.10+ desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.
echo Instalando dependencias de Python...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Fallo la instalacion de algunas dependencias.
    echo Intenta correr: pip install -r requirements.txt --user
    pause
    exit /b 1
)

echo.
echo [LISTO] Todas las dependencias instaladas correctamente.
echo Ahora puedes correr START_CVSniper.bat para iniciar la aplicacion.
echo.
pause
"""

START_BAT = r"""@echo off
echo ============================================
echo   CVSniper - Iniciando...
echo ============================================
echo.

:: Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado. Corre INSTALL_dependencies.bat primero.
    pause
    exit /b 1
)

:: Cambiar al directorio del script (por si se ejecuta desde otro lugar)
cd /d "%~dp0"

:: Iniciar el bot
echo Iniciando CVSniper...
python runAiBot.py

pause
"""

SETUP_CHROME_BAT = r"""@echo off
echo ============================================
echo   CVSniper - Setup de ChromeDriver
echo ============================================
echo Ejecutando setup de ChromeDriver...
call setup\windows-setup.bat
"""

README_QUICK = """\
# CVSniper - Inicio Rapido / Quick Start

## Requisitos / Requirements
- Windows 10/11
- Python 3.10+ → https://www.python.org/downloads/
  (Marcar "Add Python to PATH" durante instalacion)
- Google Chrome instalado

## Pasos / Steps

1. **Instalar dependencias**
   Doble click en: `INSTALL_dependencies.bat`

2. **Configurar ChromeDriver** (solo la primera vez)
   Doble click en: `SETUP_ChromeDriver.bat`
   (Ejecutar como Administrador)

3. **Iniciar CVSniper**
   Doble click en: `START_CVSniper.bat`

4. **Configurar tu perfil**
   - El bot abrira una ventana y un panel web en http://127.0.0.1:5000
   - Completa toda tu informacion en el panel web
   - Haz click en "Guardar" y luego "Iniciar Bot"

## Soporte / Support
GitHub: https://github.com/GodsScion/Auto_job_applier_linkedIn
"""


# ── Funciones ──────────────────────────────────────────────────────────────────

def should_ignore(path: Path) -> bool:
    """Retorna True si la ruta debe ser ignorada."""
    return path.name in IGNORE or path.name.startswith(".")


def copy_tree(src: Path, dst: Path):
    """Copia src → dst recursivamente, respetando las reglas de exclusion."""
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if should_ignore(item):
            continue

        dest_item = dst / item.name

        if item.is_dir():
            # Carpeta config: manejo especial
            if item.name == "config":
                copy_config(item, dest_item)
            # Carpetas de resumes/excels/logs: crear vacias
            elif item.name in {"all resumes", "all excels", "logs"}:
                dest_item.mkdir(parents=True, exist_ok=True)
                # Crear .gitkeep para que la carpeta sea visible
                (dest_item / ".gitkeep").write_text("")
            else:
                copy_tree(item, dest_item)
        else:
            shutil.copy2(item, dest_item)


def copy_config(src: Path, dst: Path):
    """Copia la carpeta config reemplazando archivos personales con templates."""
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if item.name in CONFIG_IGNORE:
            continue  # Saltear archivos personales
        if item.is_dir():
            continue  # Ignorar subcarpetas como __pycache__

        shutil.copy2(item, dst / item.name)

    # Copiar los .default.py como los archivos activos
    for cfg_name in CONFIG_REPLACEMENTS:
        default_file = src / f"{cfg_name}.default.py"
        target_file = dst / f"{cfg_name}.py"
        if default_file.exists():
            shutil.copy2(default_file, target_file)
            print(f"  [config] {cfg_name}.py <- {cfg_name}.default.py (limpio)")
        else:
            print(f"  [WARN] No encontrado: {default_file.name}")

    # Crear user_config.json limpio
    config_json = dst / "user_config.json"
    config_json.write_text(
        json.dumps(CLEAN_USER_CONFIG, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("  [config] user_config.json <- vacio/limpio")

    # resume.py limpio (solo importa personals, sin datos personales)
    resume_default = src / "resume.py"  # el original no tiene datos personales
    resume_dst = dst / "resume.py"
    if resume_default.exists():
        shutil.copy2(resume_default, resume_dst)


def create_helper_scripts(dst: Path):
    """Crea los .bat y README de ayuda."""
    (dst / "INSTALL_dependencies.bat").write_text(INSTALL_BAT, encoding="utf-8")
    (dst / "START_CVSniper.bat").write_text(START_BAT, encoding="utf-8")
    (dst / "SETUP_ChromeDriver.bat").write_text(SETUP_CHROME_BAT, encoding="utf-8")
    (dst / "LEEME_QuickStart.md").write_text(README_QUICK, encoding="utf-8")
    print("  [scripts] INSTALL, START, SETUP_Chrome, LEEME creados")


def zip_release(src: Path, zip_path: Path):
    """Comprime toda la carpeta de release en un zip."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob("*"):
            zf.write(file, file.relative_to(src.parent))
    print(f"\n[ZIP] {zip_path.name} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  CVSniper - Build Release (sin datos personales)")
    print("=" * 55)

    # Limpiar salida anterior
    if OUTPUT_DIR.exists():
        print(f"\nEliminando release anterior: {OUTPUT_DIR.name}/")
        shutil.rmtree(OUTPUT_DIR)
    if ZIP_NAME.exists():
        ZIP_NAME.unlink()

    print(f"\nCopiando archivos a: {OUTPUT_DIR.name}/")
    copy_tree(ROOT, OUTPUT_DIR)

    print("\nCreando scripts de ayuda...")
    create_helper_scripts(OUTPUT_DIR)

    print("\nComprimiendo en ZIP...")
    zip_release(OUTPUT_DIR, ZIP_NAME)

    print("\n" + "=" * 55)
    print("  BUILD COMPLETO")
    print("=" * 55)
    print(f"  Carpeta: {OUTPUT_DIR}")
    print(f"  ZIP:     {ZIP_NAME}")
    print("\nPuedes distribuir el archivo ZIP.")
    print("NO contiene ninguna credencial ni dato personal.")


if __name__ == "__main__":
    main()
