"""The installer scripts are not a package; load them by path."""

import importlib.util
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[3] / "installer"


def load_installer_module(name: str):
    spec = importlib.util.spec_from_file_location(f"installer_{name}", INSTALLER_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stamp_module():
    return load_installer_module("stamp_core_version")


@pytest.fixture
def update_module():
    return load_installer_module("update_cuvis_sdk")


@pytest.fixture
def launcher_module():
    return load_installer_module("server_launcher")
