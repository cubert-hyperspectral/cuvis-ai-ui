@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Build script for Cuvis.AI UI Windows installer
::
:: Builds the UI PyInstaller bundle and packages it together with the
:: cuvis-ai-core source tree into an Inno Setup installer. Heavy runtime
:: dependencies (torch CUDA, ffmpeg, graphviz, transformers, ...) are
:: installed at install time by installer\bootstrap.ps1, not bundled.
::
:: Prerequisites:
::   1. Python 3.11 with uv
::   2. cuvis-ai-ui venv with dev extras  (uv sync --extra dev)
::   3. cuvis-ai-core checked out as a sibling at ..\..\cuvis-ai-core\cuvis-ai-core\
::   4. Inno Setup 6 installed (https://jrsoftware.org/isinfo.php)
::
:: Run from the UI project root:  installer\build.bat
:: Output:  installer\Output\cuvis-ai-ui-setup-<version>.exe   (~150 MB)
:: ============================================================================

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "INSTALLER_DIR=%PROJECT_ROOT%\installer"
set "CORE_ROOT=%PROJECT_ROOT%\..\..\cuvis-ai-core\cuvis-ai-core"
set "PAYLOAD_DIR=%INSTALLER_DIR%\payload\cuvis-ai-core"

echo ============================================================
echo  Cuvis.AI UI - Windows Installer Build
echo ============================================================
echo.
echo UI project:    %PROJECT_ROOT%
echo Core project:  %CORE_ROOT%
echo.

:: -------------------------------------------------------
:: Step 1: Ensure UI build deps are installed
:: -------------------------------------------------------
echo [1/5] Installing build dependencies...
uv pip install pyinstaller>=6.0.0 Pillow>=10.0.0
if errorlevel 1 (
    echo ERROR: Failed to install build dependencies.
    exit /b 1
)
echo.

:: -------------------------------------------------------
:: Step 2: Stage cuvis-ai-core source for shipping
:: -------------------------------------------------------
echo [2/5] Staging cuvis-ai-core source -> installer\payload\...

:: Capture cuvis-ai-core version from git BEFORE we strip .git in the copy.
:: bootstrap.ps1 surfaces this as SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CUVIS_AI_CORE
:: so `uv sync` doesn't fail with "setuptools-scm was unable to detect version".
set "CORE_VERSION="
for /f "delims=" %%v in ('git -C "%CORE_ROOT%" describe --tags --abbrev^=0 2^>nul') do set "CORE_VERSION=%%v"
if "%CORE_VERSION:~0,1%"=="v" set "CORE_VERSION=%CORE_VERSION:~1%"
if "%CORE_VERSION%"=="" set "CORE_VERSION=0.0.0+local"

if exist "%PAYLOAD_DIR%" rmdir /s /q "%PAYLOAD_DIR%"
mkdir "%PAYLOAD_DIR%"
robocopy "%CORE_ROOT%" "%PAYLOAD_DIR%" /E /NFL /NDL /NP /NJH /NJS ^
    /XD .venv .git build dist __pycache__ .ruff_cache .mypy_cache .pytest_cache htmlcov ^
    /XF *.pyc *.pyo
:: robocopy: 0=no copy, 1=copied, 2=extra, 4=mismatched, 8+=error
if errorlevel 8 (
    echo ERROR: robocopy failed staging cuvis-ai-core source.
    exit /b 1
)
:: Don't let robocopy's success exit codes (1-7) trip subsequent error checks
set "errorlevel=0"

:: Persist the version so bootstrap.ps1 can pass it to setuptools-scm
echo %CORE_VERSION%> "%PAYLOAD_DIR%\.cuvis_ai_core_version"
echo       Staged at %PAYLOAD_DIR% (version: %CORE_VERSION%)
echo.

:: -------------------------------------------------------
:: Step 3: Convert PNG icon to ICO + detect version
:: -------------------------------------------------------
echo [3/5] Preparing icon and detecting version...
uv run python "%INSTALLER_DIR%\convert_icon.py"
if errorlevel 1 (
    echo ERROR: Icon conversion failed.
    exit /b 1
)
for /f "delims=" %%v in ('uv run python -c "from importlib.metadata import version; print(version(\"cuvis-ai-ui\"))"') do set "APP_VERSION=%%v"
if "%APP_VERSION%"=="" set "APP_VERSION=0.0.0"
echo       Version: %APP_VERSION%
echo.

:: -------------------------------------------------------
:: Step 4: Build UI with PyInstaller
:: -------------------------------------------------------
echo [4/5] Building UI bundle (PyInstaller)...
uv run pyinstaller --noconfirm --distpath "%PROJECT_ROOT%\dist" --workpath "%PROJECT_ROOT%\build" "%INSTALLER_DIR%\cuvis_ai_ui.spec"
if errorlevel 1 (
    echo ERROR: UI PyInstaller build failed.
    exit /b 1
)
if not exist "%PROJECT_ROOT%\dist\cuvis-ui\cuvis-ui.exe" (
    echo ERROR: UI bundle not found at dist\cuvis-ui\cuvis-ui.exe
    exit /b 1
)
echo       UI bundle ready: dist\cuvis-ui\cuvis-ui.exe
echo.

:: -------------------------------------------------------
:: Step 5: Run Inno Setup compiler
:: -------------------------------------------------------
echo [5/5] Building Windows installer with Inno Setup...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo WARNING: Inno Setup not found. Skipping installer creation.
    echo          Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo          Stage outputs:
    echo            dist\cuvis-ui\cuvis-ui.exe
    echo            installer\payload\cuvis-ai-core\
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
echo  Build complete
echo ============================================================
echo.
if exist "%INSTALLER_DIR%\Output\cuvis-ai-ui-setup-%APP_VERSION%.exe" (
    echo  Installer: installer\Output\cuvis-ai-ui-setup-%APP_VERSION%.exe
)
echo.
endlocal
