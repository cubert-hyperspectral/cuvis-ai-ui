# Cuvis.AI UI post-install bootstrap.
#
# Invoked by Inno Setup [Run] after files are extracted. Sets up the
# runtime environment that previously was bundled at build time:
#   1. Ensure `uv` is on PATH (installs astral-sh/uv if missing).
#   2. Copy the shipped cuvis-ai-core source into the per-user data dir.
#   3. Create a venv at <user-data>\server-venv via `uv venv --python 3.11`.
#   4. `uv sync` against the source so cuvis-ai-core + torch CUDA + cuvis SDK
#      binding + cuvis-ai-schemas all land in the venv.
#   5. Install pystray for the server tray icon.
#   6. Download FFmpeg LGPL shared and Graphviz portable into <app>\ffmpeg
#      and <app>\graphviz so torchcodec/dot are reachable at runtime.
#
# Idempotent: re-running upgrades source + uv-syncs incrementally.
# Logs to %LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\bootstrap.log so users can
# inspect failures.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,

    [switch]$SkipBinaries  # Skip ffmpeg/graphviz download (for testing)
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- paths ---
$UserData    = Join-Path $env:LOCALAPPDATA "Cubert GmbH\Cuvis.AI UI"
$SourceDir   = Join-Path $UserData "server\source"
$VenvDir     = Join-Path $UserData "server-venv"
$VenvPy      = Join-Path $VenvDir "Scripts\python.exe"
$LogFile     = Join-Path $UserData "bootstrap.log"
$ShippedSrc  = Join-Path $InstallDir "server\source"
$FfmpegDir   = Join-Path $InstallDir "ffmpeg"
$GraphvizDir = Join-Path $InstallDir "graphviz"

$null = New-Item -ItemType Directory -Force -Path $UserData

$logStream = [System.IO.StreamWriter]::new($LogFile, $true)  # append
$logStream.AutoFlush = $true

function Log {
    param([string]$msg)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    $logStream.WriteLine($line)
    Write-Host $line
}

# Run a native command with stdout+stderr merged into the log without
# letting PowerShell's $ErrorActionPreference='Stop' turn benign warnings
# (e.g. uv printing to stderr) into terminating errors.
function Invoke-Native {
    param(
        [Parameter(Mandatory=$true)] [string]$LogPrefix,
        [Parameter(Mandatory=$true)] [scriptblock]$Block
    )
    $origEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Block 2>&1 | ForEach-Object {
            $line = "$_"
            $logStream.WriteLine("[$LogPrefix] $line")
            Write-Host $line
        }
    }
    finally {
        $ErrorActionPreference = $origEAP
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$LogPrefix failed (exit $LASTEXITCODE)"
    }
}

function FetchAndExtract {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Target
    )
    $binDir = Join-Path $Target "bin"
    if (Test-Path $binDir) {
        Log "[$Name] already present at $Target - skipping"
        return
    }
    if (Test-Path $Target) { Remove-Item -Path $Target -Recurse -Force }

    $tmpZip = Join-Path $env:TEMP "cuvis_ai_bootstrap_$Name.zip"
    $tmpExtract = Join-Path $env:TEMP "cuvis_ai_bootstrap_$Name`_x"
    if (Test-Path $tmpExtract) { Remove-Item -Path $tmpExtract -Recurse -Force }

    Log "[$Name] downloading from $Url"
    Invoke-WebRequest -Uri $Url -OutFile $tmpZip -UseBasicParsing

    Log "[$Name] extracting"
    Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force

    $inner = Get-ChildItem -Path $tmpExtract -Directory | Select-Object -First 1
    if ($null -eq $inner) {
        throw "[$Name] zip had no top-level directory"
    }
    $null = New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent)
    Move-Item -Path $inner.FullName -Destination $Target

    Remove-Item $tmpZip -Force
    Remove-Item $tmpExtract -Recurse -Force
    Log "[$Name] ready at $Target"
}

try {
    Log "=== Cuvis.AI bootstrap start ==="
    Log "InstallDir: $InstallDir"
    Log "UserData:   $UserData"

    # --- 1. uv on PATH? -----------------------------------------------------
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Log "uv not found - installing via astral.sh installer..."
        Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing | Invoke-Expression

        # uv installer adds to the user-level PATH, but the current shell session
        # won't see it until we re-read it.
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $env:Path = "$userPath;$machinePath"

        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            throw "uv installation script ran but 'uv' is still not on PATH."
        }
    }
    Log "uv version: $(& uv --version)"

    # --- 2. Copy cuvis-ai-core source into per-user data dir ---------------
    if (-not (Test-Path $ShippedSrc)) {
        throw "Shipped server source not found at $ShippedSrc"
    }
    Log "Copying cuvis-ai-core source -> $SourceDir"
    if (Test-Path $SourceDir) { Remove-Item -Path $SourceDir -Recurse -Force }
    $null = New-Item -ItemType Directory -Force -Path (Split-Path $SourceDir -Parent)
    # robocopy: /E (subdirs incl empty), /NFL/NDL (less noise), /NP (no progress);
    # exit codes 0-7 are success.
    $rcArgs = @($ShippedSrc, $SourceDir, "/E", "/NFL", "/NDL", "/NP", "/NJH", "/NJS")
    & robocopy @rcArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit $LASTEXITCODE" }
    $LASTEXITCODE = 0  # robocopy may have set it to 1 on success

    # --- 3. Create venv -----------------------------------------------------
    if (-not (Test-Path $VenvPy)) {
        Log "Creating venv at $VenvDir (python 3.11)..."
        & uv venv --python 3.11 $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "uv venv failed (exit $LASTEXITCODE)" }
    } else {
        Log "Reusing existing venv at $VenvDir"
    }

    # --- 4. uv sync to install cuvis-ai-core + transitive deps -------------
    # cuvis-ai-core uses setuptools_scm for its version, but we ship the source
    # without .git, so we need to tell setuptools-scm what to pretend the
    # version is. build.bat captures it from `git describe` and stashes it.
    $verFile = Join-Path $SourceDir ".cuvis_ai_core_version"
    if (Test-Path $verFile) {
        $coreVer = (Get-Content $verFile -Raw).Trim()
        if ($coreVer) {
            Log "Pretending cuvis-ai-core version = $coreVer (setuptools-scm)"
            $env:SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CUVIS_AI_CORE = $coreVer
        }
    }

    Log "Running uv sync against $SourceDir (this may take several minutes)..."
    Push-Location $SourceDir
    try {
        $env:UV_PROJECT_ENVIRONMENT = $VenvDir
        # Clear VIRTUAL_ENV so uv doesn't print a warning about it disagreeing
        # with UV_PROJECT_ENVIRONMENT (which it will then ignore anyway).
        $origVenv = $env:VIRTUAL_ENV
        $env:VIRTUAL_ENV = $null
        try {
            Invoke-Native -LogPrefix "uv sync" -Block { uv sync }
        }
        finally {
            $env:VIRTUAL_ENV = $origVenv
        }
    } finally {
        Pop-Location
        Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
        Remove-Item Env:\SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CUVIS_AI_CORE -ErrorAction SilentlyContinue
    }

    # --- 5. pystray for the tray icon --------------------------------------
    Log "Installing pystray into the server venv..."
    Invoke-Native -LogPrefix "uv pip install pystray" -Block {
        uv pip install --python $VenvPy "pystray>=0.19.5"
    }

    # --- 6. ffmpeg + graphviz portable downloads ---------------------------
    if (-not $SkipBinaries) {
        FetchAndExtract -Name "ffmpeg" `
            -Url "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl-shared.zip" `
            -Target $FfmpegDir
        FetchAndExtract -Name "graphviz" `
            -Url "https://gitlab.com/api/v4/projects/4207231/packages/generic/graphviz-releases/12.2.1/windows_10_cmake_Release_Graphviz-12.2.1-win64.zip" `
            -Target $GraphvizDir
    }

    # --- 7. smoke test ------------------------------------------------------
    Log "Smoke-test: importing cuvis_ai_core in the new venv..."
    Invoke-Native -LogPrefix "smoke" -Block {
        & $VenvPy -c "import cuvis, cuvis_ai_core, torch; print('cuvis_ai_core OK; torch ' + torch.__version__ + ' CUDA=' + str(torch.cuda.is_available()))"
    }

    Log "=== bootstrap complete ==="
}
catch {
    Log "BOOTSTRAP FAILED: $_"
    Log $_.ScriptStackTrace
    throw
}
finally {
    $logStream.Close()
}
