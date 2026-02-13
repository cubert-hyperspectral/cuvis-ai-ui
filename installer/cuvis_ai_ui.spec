# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Cuvis.AI UI."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).parent
PACKAGE_DIR = PROJECT_ROOT / "cuvis_ai_ui"
LAUNCHER = Path(SPECPATH) / "launcher.py"
ICON_FILE = Path(SPECPATH) / "logo.ico"

# cuvis-ai-schemas is an editable local dependency that PyInstaller cannot
# discover automatically.  Locate it relative to the project root (matches
# the uv source path ../../cuvis-ai-schemas) and add it to the search path.
SCHEMAS_ROOT = PROJECT_ROOT.parent.parent / "cuvis-ai-schemas"

# collect_all gathers all submodules, data files, and binaries for a package.
schemas_datas, schemas_binaries, schemas_hiddenimports = collect_all("cuvis_ai_schemas")

# Remove torch and related packages that collect_all pulls in via
# cuvis_ai_schemas.pipeline.ports.  Torch is ~2 GB and not needed by the UI.
# A lightweight runtime hook (rthook_torch_stub.py) provides the few symbols
# the schema code actually references (torch.dtype, torch.Tensor).
_torch_prefixes = ("torch", "functorch", "caffe2", "nvidia", "triton")
schemas_hiddenimports = [
    m for m in schemas_hiddenimports
    if not any(m == p or m.startswith(p + ".") for p in _torch_prefixes)
]
schemas_binaries = [
    (src, dst) for src, dst in schemas_binaries
    if not any(p in src for p in _torch_prefixes)
]
schemas_datas = [
    (src, dst) for src, dst in schemas_datas
    if not any(p in src for p in _torch_prefixes)
]

RUNTIME_HOOK = Path(SPECPATH) / "rthook_torch_stub.py"

# --- Data files to bundle ---------------------------------------------------
datas = [
    # Application icon (referenced at runtime via Path(__file__).parent / resources / icons)
    (str(PACKAGE_DIR / "resources" / "icons" / "logo.png"), os.path.join("cuvis_ai_ui", "resources", "icons")),
    # Plugin catalog (referenced as Path(__file__).parent.parent / cuvis_ai_catalog.yaml)
    (str(PROJECT_ROOT / "cuvis_ai_catalog.yaml"), "."),
] + schemas_datas

# --- Hidden imports ----------------------------------------------------------
# PyInstaller cannot detect these because they are loaded dynamically or via
# string-based imports.
hiddenimports = [
    # cuvis-ai-schemas submodules (local editable dependency)
    "cuvis_ai_schemas",
    "cuvis_ai_schemas.enums",
    "cuvis_ai_schemas.plugin",
    "cuvis_ai_schemas.discovery",
    "cuvis_ai_schemas.extensions",
    "cuvis_ai_schemas.extensions.ui",
    "cuvis_ai_schemas.grpc",
    "cuvis_ai_schemas.grpc.v1",
    "cuvis_ai_schemas.grpc.v1.cuvis_ai_pb2",
    "cuvis_ai_schemas.grpc.v1.cuvis_ai_pb2_grpc",
    "cuvis_ai_schemas.execution",
    "cuvis_ai_schemas.pipeline",
    "cuvis_ai_schemas.pipeline.ports",
    "cuvis_ai_schemas.training",
    # gRPC / protobuf internals
    "grpc",
    "grpc._cython",
    "grpc._cython._cygrpc",
    "google.protobuf",
    "google.protobuf.descriptor",
    "google.protobuf.descriptor_pool",
    "google.protobuf.reflection",
    "google.protobuf.symbol_database",
    "google.protobuf.internal",
    "google.protobuf.internal.builder",
    "google.protobuf.internal.containers",
    "google.protobuf.internal.enum_type_wrapper",
    # PySide6 essentials
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    # NodeGraphQt
    "NodeGraphQt",
    # pydantic (uses dynamic imports)
    "pydantic",
    "pydantic.deprecated",
    "pydantic.deprecated.decorator",
    "pydantic_core",
    # loguru
    "loguru",
    # yaml
    "yaml",
]

# --- Excludes (dev/test tools not needed at runtime) -------------------------
excludes = [
    # Heavy ML packages (UI doesn't need them; torch stub provided via runtime hook)
    "torch", "torchvision", "torchaudio", "functorch",
    "caffe2", "nvidia", "triton",
    "numpy", "scipy", "pandas", "matplotlib",
    # Dev/test tools
    "pytest", "pytest_cov", "pytest_qt",
    "mypy", "ruff", "ipdb", "IPython",
    "tkinter",
]

# --- Analysis ----------------------------------------------------------------
a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(PROJECT_ROOT), str(SCHEMAS_ROOT)],
    binaries=schemas_binaries,
    datas=datas,
    hiddenimports=hiddenimports + schemas_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(RUNTIME_HOOK)],
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
    name="cuvis-ui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    icon=str(ICON_FILE) if ICON_FILE.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cuvis-ui",
)
