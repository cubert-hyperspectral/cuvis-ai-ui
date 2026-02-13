"""Persistent plugin settings for cuvis-ai visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from cuvis_ai_ui.settings.common import app_config_dir

PLUGIN_STORE_VERSION = 1


def get_plugin_store_path() -> Path:
    """Return the path for the plugin persistence file."""
    return app_config_dir() / "plugins.json"


def get_default_plugin_entries() -> list[dict[str, Any]]:
    """Load the default plugins from the built-in catalog manifest."""
    manifest_path = Path(__file__).resolve().parent.parent.parent / "cuvis_ai_catalog.yaml"
    if not manifest_path.exists():
        return []

    try:
        import yaml

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning(f"Failed to read default plugin manifest: {exc}")
        return []

    plugins = manifest.get("plugins", {})
    if not isinstance(plugins, dict):
        return []

    entries: list[dict[str, Any]] = []
    for name, config in plugins.items():
        if not isinstance(name, str) or not isinstance(config, dict):
            continue
        entries.append(
            {
                "name": name,
                "enabled": True,
                "source": "manifest",
                "config": config,
                "origin": str(manifest_path),
            }
        )
    return entries


def _normalize_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        return None

    config = entry.get("config")
    if not isinstance(config, dict):
        config = {}

    source = entry.get("source")
    if not isinstance(source, str) or not source:
        source = "plugin"

    origin = entry.get("origin")
    if not isinstance(origin, str):
        origin = None

    enabled = bool(entry.get("enabled", True))

    return {
        "name": name,
        "enabled": enabled,
        "source": source,
        "config": config,
        "origin": origin,
    }


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for entry in entries:
        name = entry["name"]
        if name in seen:
            result[seen[name]] = entry
        else:
            seen[name] = len(result)
            result.append(entry)
    return result


def load_plugin_entries() -> list[dict[str, Any]]:
    """Load persisted plugin entries, falling back to defaults."""
    path = get_plugin_store_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning(f"Failed to read plugin settings: {exc}")
            return get_default_plugin_entries()

        if isinstance(data, dict):
            plugins = data.get("plugins", [])
        elif isinstance(data, list):
            plugins = data
        else:
            plugins = []

        if isinstance(plugins, list):
            entries = [_normalize_entry(p) for p in plugins]
            normalized = [e for e in entries if e is not None]
            return _dedupe_entries(normalized)

    return get_default_plugin_entries()


def save_plugin_entries(entries: list[dict[str, Any]]) -> None:
    """Persist plugin entries to disk."""
    normalized = [_normalize_entry(e) for e in entries]
    payload = {
        "version": PLUGIN_STORE_VERSION,
        "plugins": [e for e in normalized if e is not None],
    }
    path = get_plugin_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def reset_plugin_entries() -> list[dict[str, Any]]:
    """Reset plugin entries to defaults and persist."""
    defaults = get_default_plugin_entries()
    save_plugin_entries(defaults)
    return defaults


def merge_plugin_entries(
    existing: list[dict[str, Any]],
    updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge updates into existing entries while preserving order."""
    normalized_existing = [e for e in (_normalize_entry(e) for e in existing) if e]
    normalized_updates = [e for e in (_normalize_entry(e) for e in updates) if e]

    update_map = {entry["name"]: entry for entry in normalized_updates}
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    for entry in normalized_existing:
        name = entry["name"]
        merged.append(update_map.get(name, entry))
        seen.add(name)

    for entry in normalized_updates:
        if entry["name"] not in seen:
            merged.append(entry)

    return merged


def build_manifest(
    entries: list[dict[str, Any]],
    enabled_only: bool = True,
) -> dict[str, Any]:
    """Build a plugin manifest dictionary from persisted entries."""
    manifest: dict[str, Any] = {"plugins": {}}
    for entry in entries:
        normalized = _normalize_entry(entry)
        if not normalized:
            continue
        if enabled_only and not normalized["enabled"]:
            continue
        config = dict(normalized["config"])
        origin = normalized.get("origin")
        path_value = config.get("path")
        if origin and isinstance(path_value, str):
            path_obj = Path(path_value)
            if not path_obj.is_absolute():
                config["path"] = str(Path(origin).parent / path_obj)
        provides = config.get("provides")
        if isinstance(provides, list) and not provides:
            config.pop("provides", None)
        manifest["plugins"][normalized["name"]] = config
    return manifest


def write_manifest_temp(manifest: dict[str, Any]) -> Path:
    """Write a manifest dictionary to a temporary JSON file."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(manifest, f)
        return Path(f.name)
