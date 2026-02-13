@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Build script for Cuvis.AI UI Windows installer
::
:: Builds TWO PyInstaller bundles (UI + gRPC server) then wraps them in a
:: single Inno Setup installer.
::
:: Prerequisites:
::   1. Python 3.11 with uv
::   2. cuvis-ai-ui venv with dev extras  (uv sync --extra dev)
::   3. cuvis-ai-core venv with torch CUDA 12.8 installed
::   4. Inno Setup 6 installed (https://jrsoftware.org/isinfo.php)
::
:: Run from the UI project root:  installer\build.bat
:: Output:  installer\Output\cuvis-ai-ui-setup-<version>.exe
:: ============================================================================

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "INSTALLER_DIR=%PROJECT_ROOT%\installer"
set "CORE_ROOT=%PROJECT_ROOT%\..\..\cuvis-ai-core\cuvis-ai-core"

echo ============================================================
echo  Cuvis.AI UI - Windows Installer Build
echo ============================================================
echo.
echo UI project:   %PROJECT_ROOT%
echo Core project:  %CORE_ROOT%
echo.

:: -------------------------------------------------------
:: Step 1: Ensure build dependencies are installed
:: -------------------------------------------------------
echo [1/7] Installing build dependencies...
uv pip install pyinstaller>=6.0.0 Pillow>=10.0.0
if errorlevel 1 (
    echo ERROR: Failed to install build dependencies.
    exit /b 1
)
echo.

:: -------------------------------------------------------
:: Step 2: Convert PNG icon to ICO
:: -------------------------------------------------------
echo [2/7] Converting logo.png to logo.ico...
uv run python "%INSTALLER_DIR%\convert_icon.py"
if errorlevel 1 (
    echo ERROR: Icon conversion failed.
    exit /b 1
)
echo.

:: -------------------------------------------------------
:: Step 3: Detect version from setuptools-scm
:: -------------------------------------------------------
echo [3/7] Detecting version...
for /f "delims=" %%v in ('uv run python -c "from importlib.metadata import version; print(version(\"cuvis-ai-ui\"))"') do set "APP_VERSION=%%v"
if "%APP_VERSION%"=="" (
    echo WARNING: Could not detect version, using 0.0.0
    set "APP_VERSION=0.0.0"
)
echo       Version: %APP_VERSION%
echo.

:: -------------------------------------------------------
:: Step 4: Build UI with PyInstaller
:: -------------------------------------------------------
echo [4/7] Building UI bundle (PyInstaller)...
uv run pyinstaller --noconfirm --distpath "%PROJECT_ROOT%\dist" --workpath "%PROJECT_ROOT%\build" "%INSTALLER_DIR%\cuvis_ai_ui.spec"
if errorlevel 1 (
    echo ERROR: UI PyInstaller build failed.
    exit /b 1
)
echo.

:: -------------------------------------------------------
:: Step 5: Build Server with PyInstaller
:: -------------------------------------------------------
echo [5/7] Building server bundle (PyInstaller)...
echo       This may take a while (bundling PyTorch CUDA 12.8)...
uv run pyinstaller --noconfirm --distpath "%PROJECT_ROOT%\dist" --workpath "%PROJECT_ROOT%\build" "%INSTALLER_DIR%\cuvis_ai_core.spec"
if errorlevel 1 (
    echo ERROR: Server PyInstaller build failed.
    exit /b 1
)
echo.

:: -------------------------------------------------------
:: Step 6: Verify both bundles exist
:: -------------------------------------------------------
echo [6/7] Verifying bundles...
if not exist "%PROJECT_ROOT%\dist\cuvis-ui\cuvis-ui.exe" (
    echo ERROR: UI bundle not found at dist\cuvis-ui\cuvis-ui.exe
    exit /b 1
)
if not exist "%PROJECT_ROOT%\dist\cuvis-server\cuvis-server.exe" (
    echo ERROR: Server bundle not found at dist\cuvis-server\cuvis-server.exe
    exit /b 1
)
echo       UI bundle:     dist\cuvis-ui\cuvis-ui.exe
echo       Server bundle: dist\cuvis-server\cuvis-server.exe
echo.

:: -------------------------------------------------------
:: Step 7: Run Inno Setup compiler
:: -------------------------------------------------------
echo [7/7] Building Windows installer with Inno Setup...

:: Try common Inno Setup install locations
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo WARNING: Inno Setup not found. Skipping installer creation.
    echo          The PyInstaller bundles are ready at:
    echo            dist\cuvis-ui\cuvis-ui.exe
    echo            dist\cuvis-server\cuvis-server.exe
    echo          Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo          then re-run this script to create the installer.
    goto :done
)

"%ISCC%" /DMyAppVersion=%APP_VERSION% "%INSTALLER_DIR%\cuvis_ai_ui.iss"
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed.
    exit /b 1
)
echo.

:done
echo ============================================================
echo  Build complete!
echo ============================================================
echo.
if exist "%INSTALLER_DIR%\Output\cuvis-ai-ui-setup-%APP_VERSION%.exe" (
    echo  Installer: installer\Output\cuvis-ai-ui-setup-%APP_VERSION%.exe
) else (
    echo  Bundles ready at dist\cuvis-ui\ and dist\cuvis-server\
)
echo.
endlocal
