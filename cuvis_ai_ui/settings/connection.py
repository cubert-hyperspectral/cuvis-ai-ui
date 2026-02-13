"""Persistent connection settings for cuvis-ai visualizer."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from cuvis_ai_ui.settings.common import app_config_dir

CONNECTION_STORE_VERSION = 1

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 50051


def _connection_store_path():
    return app_config_dir() / "connection.json"


def get_default_connection_settings() -> dict[str, Any]:
    """Return the default connection settings."""
    return {
        "version": CONNECTION_STORE_VERSION,
        "mode": "local",
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "auto_start": True,
    }


def load_connection_settings() -> dict[str, Any]:
    """Load persisted connection settings, falling back to defaults."""
    path = _connection_store_path()
    defaults = get_default_connection_settings()

    if not path.exists():
        return defaults

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning(f"Failed to read connection settings: {exc}")
        return defaults

    if not isinstance(data, dict):
        return defaults

    # Merge loaded values over defaults so new keys are always present
    merged = dict(defaults)
    if data.get("mode") in ("local", "remote"):
        merged["mode"] = data["mode"]
    if isinstance(data.get("host"), str) and data["host"]:
        merged["host"] = data["host"]
    if isinstance(data.get("port"), int) and 1 <= data["port"] <= 65535:
        merged["port"] = data["port"]
    if isinstance(data.get("auto_start"), bool):
        merged["auto_start"] = data["auto_start"]

    return merged


def save_connection_settings(settings: dict[str, Any]) -> None:
    """Persist connection settings to disk."""
    payload = {
        "version": CONNECTION_STORE_VERSION,
        "mode": settings.get("mode", "local"),
        "host": settings.get("host", DEFAULT_HOST),
        "port": settings.get("port", DEFAULT_PORT),
        "auto_start": settings.get("auto_start", True),
    }
    path = _connection_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
