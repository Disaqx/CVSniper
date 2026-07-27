@echo off
:: CVSniper - dependency installer for Windows
:: Run this once after cloning. It checks Python, installs what the bot needs
:: and seeds the config files from the templates.
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
title CVSniper setup

echo.
echo ===============================================
echo   CVSniper - setup
echo ===============================================
echo.

:: --- Python ------------------------------------------------------------
:: The launcher (py) is preferred: on Windows "python" can be the Store stub
:: that opens the Microsoft Store instead of running anything.
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo   ERROR: Python was not found.
  echo   Install it from https://www.python.org/downloads/
  echo   and tick "Add Python to PATH" during the install.
  echo.
  pause
  exit /b 1
)

for /f "tokens=2" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo   Python found: !PYVER!

:: --- Dependencies -------------------------------------------------------
echo.
echo   Installing dependencies (this takes a couple of minutes)...
echo.
%PY% -m pip install --upgrade pip --quiet
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   ERROR: the dependencies could not be installed.
  echo   Check your internet connection and the error above.
  echo.
  pause
  exit /b 1
)

:: --- Config files -------------------------------------------------------
:: Only the *.default.py templates are versioned. The real config files hold
:: personal data and API keys, so they stay out of git and are created here.
echo.
echo   Preparing the config files...
for %%f in (personals questions search settings secrets) do (
  if not exist "config\%%f.py" (
    if exist "config\%%f.default.py" (
      copy /y "config\%%f.default.py" "config\%%f.py" >nul
      echo     created config\%%f.py
    )
  ) else (
    echo     config\%%f.py already exists, left untouched
  )
)

echo.
echo ===============================================
echo   Done. Start the bot with:
echo.
echo       %PY% runAiBot.py
echo.
echo   Everything is configured from the settings
echo   window, no need to edit files by hand.
echo ===============================================
echo.
pause
