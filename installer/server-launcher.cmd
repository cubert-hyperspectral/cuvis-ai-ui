@echo off
:: Cuvis.AI Server launcher — invoked from the Start Menu shortcut.
:: 1. Prepend bundled FFmpeg + Graphviz to PATH (torchcodec + graphviz Python wrapper need them).
:: 2. Run server_launcher.py in the per-user server-venv (created by bootstrap.ps1).

setlocal

set "APP_DIR=%~dp0.."
set "VENV_PY=%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server-venv\Scripts\pythonw.exe"

if not exist "%VENV_PY%" (
    echo Cuvis.AI server-venv not found at %VENV_PY%.
    echo Re-run the installer to bootstrap the server environment, or check
    echo %LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\bootstrap.log for errors.
    pause
    exit /b 1
)

set "PATH=%APP_DIR%\ffmpeg\bin;%APP_DIR%\graphviz\bin;%PATH%"

start "" "%VENV_PY%" "%~dp0server_launcher.py"
