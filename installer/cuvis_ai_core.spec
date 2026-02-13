# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for cuvis-ai-core gRPC server (with CUDA 12.8 torch)."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Paths — the spec lives in cuvis-ai-ui/installer/ but the server source is
# in cuvis-ai-core.
SPEC_DIR = Path(SPECPATH)
UI_PROJECT_ROOT = SPEC_DIR.parent
CORE_ROOT = UI_PROJECT_ROOT.parent.parent / "cuvis-ai-core" / "cuvis-ai-core"
SCHEMAS_ROOT = UI_PROJECT_ROOT.parent.parent / "cuvis-ai-schemas"
LAUNCHER = SPEC_DIR / "server_launcher.py"

# --- Collect packages --------------------------------------------------------
# These are large packages with many dynamic imports that PyInstaller cannot
# trace statically.

core_datas, core_binaries, core_hiddenimports = collect_all("cuvis_ai_core")
schemas_datas, schemas_binaries, schemas_hiddenimports = collect_all("cuvis_ai_schemas")
torch_datas, torch_binaries, torch_hiddenimports = collect_all("torch")
tv_datas, tv_binaries, tv_hiddenimports = collect_all("torchvision")

# --- Data files --------------------------------------------------------------
datas = (
    core_datas
    + schemas_datas
    + torch_datas
    + tv_datas
    + [
        # Runtime config files
        (str(CORE_ROOT / "configs"), "configs"),
    ]
)

# --- Binaries (CUDA libs, torch C++ extensions, etc.) ------------------------
binaries = core_binaries + schemas_binaries + torch_binaries + tv_binaries

# --- Hidden imports ----------------------------------------------------------
hiddenimports = (
    core_hiddenimports
    + schemas_hiddenimports
    + torch_hiddenimports
    + tv_hiddenimports
    + [
        # cuvis-ai-core internal submodules
        "cuvis_ai_core.grpc.production_server",
        "cuvis_ai_core.grpc.service",
        "cuvis_ai_core.grpc.health",
        "cuvis_ai_core.grpc.session_manager",
        "cuvis_ai_core.grpc.plugin_service",
        "cuvis_ai_core.grpc.config_service",
        "cuvis_ai_core.grpc.pipeline_service",
        "cuvis_ai_core.grpc.inference_service",
        "cuvis_ai_core.grpc.training_service",
        "cuvis_ai_core.grpc.discovery_service",
        "cuvis_ai_core.grpc.introspection_service",
        "cuvis_ai_core.grpc.session_service",
        "cuvis_ai_core.grpc.trainrun_service",
        "cuvis_ai_core.grpc.helpers",
        "cuvis_ai_core.grpc.callbacks",
        # gRPC internals
        "grpc",
        "grpc._cython",
        "grpc._cython._cygrpc",
        "grpc_health",
        "grpc_health.v1",
        "grpc_health.v1.health_pb2",
        "grpc_health.v1.health_pb2_grpc",
        "google.protobuf",
        "google.protobuf.descriptor",
        "google.protobuf.descriptor_pool",
        "google.protobuf.reflection",
        "google.protobuf.symbol_database",
        "google.protobuf.internal",
        "google.protobuf.internal.builder",
        "google.protobuf.internal.containers",
        "google.protobuf.internal.enum_type_wrapper",
        # PyTorch Lightning
        "pytorch_lightning",
        "lightning",
        "lightning.pytorch",
        "lightning_utilities",
        # Hydra / OmegaConf
        "hydra",
        "hydra.core",
        "hydra.core.config_store",
        "hydra._internal",
        "omegaconf",
        # Science / image processing
        "numpy",
        "PIL",
        "skimage",
        "pycocotools",
        # Pydantic
        "pydantic",
        "pydantic_core",
        # Config
        "dotenv",
        "yaml",
        "loguru",
        # Git (for plugin loading)
        "git",
        "gitdb",
        "smmap",
    ]
    + collect_submodules("hydra")
    + collect_submodules("omegaconf")
    + collect_submodules("pytorch_lightning")
)

# --- Excludes ----------------------------------------------------------------
excludes = [
    # Dev / test tools (not needed in production server)
    "pytest", "pytest_cov", "pytest_mock", "pytest_asyncio",
    "mypy", "ruff", "ipdb", "IPython",
    "ipykernel", "jupyterlab", "jupyter",
    "ipympl",
    "twine", "pip_audit", "bandit", "detect_secrets",
    "pip_licenses", "cyclonedx_bom",
    # UI frameworks (server is headless)
    "PySide6", "PyQt5", "PyQt6", "tkinter",
    "NodeGraphQt",
]

# --- Analysis ----------------------------------------------------------------
a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(CORE_ROOT), str(SCHEMAS_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cuvis-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Server is headless, logs to stdout
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cuvis-server",
)
