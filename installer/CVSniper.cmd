@echo off
:: Launcher the installer's Start-menu and desktop shortcuts point at.
:: Runs the bot on the Python bundled in .\python, never on whatever Python the
:: user may have installed: -E ignores PYTHONPATH/PYTHONHOME, -s ignores the
:: user's site-packages, so neither can shadow the bundled libraries.
cd /d "%~dp0"
title CVSniper
"%~dp0python\python.exe" -E -s "%~dp0runAiBot.py"
if errorlevel 1 (
  powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('CVSniper se detuvo por un error. El detalle esta en la carpeta logs.' + [Environment]::NewLine + 'CVSniper stopped with an error. Details are in the logs folder.', 'CVSniper', 'OK', 'Error') | Out-Null"
  start "" "%~dp0logs"
)
