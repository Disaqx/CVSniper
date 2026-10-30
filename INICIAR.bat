@echo off
:: CVSniper - doble clic para arrancar / double-click to start
::
:: Pensado para quien nunca ha usado una terminal: comprueba Python, instala
:: lo que falte la primera vez y arranca el bot. Si algo falla, la ventana se
:: queda abierta con el error en vez de cerrarse sola.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title CVSniper

:: --- Python ------------------------------------------------------------
:: "py" primero: en Windows "python" puede ser el atajo de la Microsoft Store,
:: que abre la tienda en vez de ejecutar nada.
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY goto :sin_python
%PY% -c "import sys" >nul 2>&1 || goto :sin_python

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo.
  echo   Tu Python es demasiado viejo. CVSniper necesita Python 3.10 o mas nuevo.
  echo   Your Python is too old. CVSniper needs Python 3.10 or newer.
  echo.
  echo   Descargalo de / Get it from: https://www.python.org/downloads/
  goto :fin_error
)

:: --- Google Chrome (solo aviso) -----------------------------------------
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if not defined CHROME (
  echo.
  echo   AVISO: no encontre Google Chrome. El bot lo necesita.
  echo   WARNING: Google Chrome was not found. The bot needs it.
  echo   https://www.google.com/chrome/
  echo.
)

:: --- Dependencias: solo la primera vez -----------------------------------
%PY% -c "import selenium, flask, pyautogui, undetected_chromedriver, openai, fitz, fpdf" >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Primera vez: instalando lo que necesita el bot. Tarda un par de minutos...
  echo   First run: installing what the bot needs. This takes a couple of minutes...
  echo.
  %PY% -m pip install --upgrade pip --quiet
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   ERROR: no se pudieron instalar las dependencias. Revisa tu conexion a internet
    echo   y el mensaje de arriba.
    echo   ERROR: the dependencies could not be installed. Check your internet connection
    echo   and the message above.
    goto :fin_error
  )
)

:: --- Arrancar ----------------------------------------------------------
echo.
echo   Iniciando CVSniper... / Starting CVSniper...
echo.
%PY% runAiBot.py
if errorlevel 1 goto :fin_error
exit /b 0

:sin_python
echo.
echo   No encontre Python. / Python was not found.
echo.
echo   1. Descargalo de / Download it from: https://www.python.org/downloads/
echo   2. Al instalar, marca la casilla "Add Python to PATH".
echo      While installing, tick the "Add Python to PATH" box.
echo   3. Vuelve a hacer doble clic en INICIAR.bat / Double-click INICIAR.bat again.

:fin_error
echo.
echo   El bot se detuvo con un error. El detalle esta arriba y en logs\log.txt
echo   The bot stopped with an error. Details above and in logs\log.txt
echo.
pause
exit /b 1
