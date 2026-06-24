"""Persistent plugin settings for cuvis-ai visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from cuvis_ai_ui.settings.common import app_config_dir

PLUGIN_STORE_VERSION = 2


def get_plugin_store_path() -> Path:
    """Return the path for the plugin persistence file."""
    return app_config_dir() / "plugins.json"


def _resolve_local_path(config: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    """Resolve a plugin config's ``path`` to an absolute path.

    Local plugin manifests may use relative paths (e.g. ``path: "../.."``)
    that are meant to be interpreted relative to the YAML file's location.
    This context is lost once the manifest crosses the gRPC boundary, so we
    resolve paths here — on the UI side — before the manifest is serialized.

    Args:
        config: Plugin config dict (may contain ``path``, ``repo``, etc.).
        manifest_dir: Directory of the YAML file the config came from.

    Returns:
        Shallow-copied config with ``path`` replaced by its absolute
        resolved form, or the original dict if ``path`` is missing,
        already absolute, or not a string.
    """
    path_value = config.get("path")
    if not isinstance(path_value, str):
        return config

    path_obj = Path(path_value)
    if path_obj.is_absolute():
        return config

    resolved = dict(config)
    resolved["path"] = str((manifest_dir / path_obj).resolve())
    return resolved


def _coerce_capabilities(config: dict[str, Any]) -> dict[str, Any]:
    """Wrap bare-string ``capabilities`` entries as ``{"class_name": ...}`` dicts.

    The plugin manifest schema requires each ``capabilities`` entry to be a
    PluginCapabilityEntry object (an FQCN ``class_name`` plus optional palette
    metadata). Legacy manifests and the Plugin Manager's free-text input use a
    plain list of class-name strings; wrap those so they validate server-side.
    Entries that are already dicts are left untouched, so this is idempotent.

    Args:
        config: Plugin config dict (may contain a ``capabilities`` list).

    Returns:
        The original dict if nothing needed wrapping, otherwise a shallow copy
        with each string ``capabilities`` entry replaced by ``{"class_name": ...}``.
    """
    capabilities = config.get("capabilities")
    if not isinstance(capabilities, list):
        return config
    coerced = [{"class_name": entry} if isinstance(entry, str) else entry for entry in capabilities]
    if coerced == capabilities:
        return config
    result = dict(config)
    result["capabilities"] = coerced
    return result


def _load_manifest_entries(manifest_path: Path) -> list[dict[str, Any]]:
    """Load the plugin entry from a single bare manifest YAML file.

    One manifest file is one plugin. The whole file is parsed as a single bare
    manifest dict: ``name`` is the logical plugin name and the remaining keys
    (``path`` / ``repo`` / ``tag`` / ``package_name`` / ``capabilities``) make
    up the persisted ``config``.

    Args:
        manifest_path: Path to a plugin manifest YAML file.

    Returns:
        A single-element list with the parsed plugin entry, or an empty list if
        the file does not parse to a dict with a string ``name``.
    """
    try:
        import yaml

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning(f"Failed to read manifest {manifest_path}: {exc}")
        return []

    if not isinstance(manifest, dict):
        return []

    name = manifest.get("name")
    if not isinstance(name, str) or not name:
        return []

    config = {k: v for k, v in manifest.items() if k != "name"}
    return [
        {
            "name": name,
            "enabled": True,
            "source": "manifest",
            "config": config,
            "origin": str(manifest_path),
        }
    ]


def get_default_plugin_entries() -> list[dict[str, Any]]:
    """Load the default plugins from the built-in catalog manifest."""
    manifest_path = Path(__file__).resolve().parent.parent.parent / "cuvis_ai_catalog.yaml"
    if not manifest_path.exists():
        return []
    return _load_manifest_entries(manifest_path)


def load_plugin_entries_from_directory(directory: str | Path) -> list[dict[str, Any]]:
    """Load plugin entries from all manifest files in a directory.

    Scans for ``*.yaml`` and ``*.yml`` files, loads each as a plugin
    manifest, and returns merged entries.  Later files override earlier
    ones when plugin names collide.

    Args:
        directory: Path to directory containing manifest YAML files.

    Returns:
        Merged and deduplicated list of plugin entries.
    """
    directory = Path(directory)
    if not directory.is_dir():
        logger.warning(f"Plugin directory does not exist: {directory}")
        return []

    all_entries: list[dict[str, Any]] = []
    for manifest_path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        entries = _load_manifest_entries(manifest_path)
        all_entries.extend(entries)

    return _dedupe_entries(all_entries)


def _migrate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Migrate a persisted entry from an older store version in place-safely.

    Version 1 stored a plugin's provided nodes under ``config["provides"]``.
    The plugin schema renamed that key to ``capabilities``; rewrite any legacy
    ``config["provides"]`` to ``config["capabilities"]`` so loading an old
    ``plugins.json`` yields the new shape. Idempotent: an entry that already
    uses ``capabilities`` (or has neither key) is returned unchanged.

    Args:
        entry: A persisted plugin entry dict.

    Returns:
        The entry with ``config["provides"]`` renamed to
        ``config["capabilities"]`` when present.
    """
    config = entry.get("config")
    if not isinstance(config, dict) or "provides" not in config:
        return entry
    migrated_config = {k: v for k, v in config.items() if k != "provides"}
    # Don't clobber an existing capabilities key; prefer it when both are set.
    migrated_config.setdefault("capabilities", config["provides"])
    return {**entry, "config": migrated_config}


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
            normalized = [_migrate_entry(e) for e in entries if e is not None]
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
) -> list[dict[str, Any]]:
    """Build the plugin-load payload: a list of bare plugin manifests.

    Each enabled entry becomes one bare manifest ``{"name": ..., **config}`` —
    the wire shape the server expects (no ``plugins:`` wrapper). Relative local
    paths are resolved against the entry's origin and bare-string
    ``capabilities`` are wrapped into ``{"class_name": ...}`` dicts; an empty
    ``capabilities`` list is dropped.
    """
    manifests: list[dict[str, Any]] = []
    for entry in entries:
        normalized = _normalize_entry(entry)
        if not normalized:
            continue
        if enabled_only and not normalized["enabled"]:
            continue
        config = dict(normalized["config"])
        origin = normalized.get("origin")
        if origin:
            config = _resolve_local_path(config, Path(origin).parent)
        config = _coerce_capabilities(config)
        capabilities = config.get("capabilities")
        if isinstance(capabilities, list) and not capabilities:
            config.pop("capabilities", None)
        manifests.append({"name": normalized["name"], **config})
    return manifests


def write_manifest_temp(manifest: list[dict[str, Any]] | dict[str, Any]) -> Path:
    """Write a manifest payload to a temporary JSON file.

    The payload is the plugin set the UI registers: a list of bare plugin
    manifests (see :func:`build_manifest`). The gRPC client reads this file back
    and registers each manifest with one ``LoadPlugin`` call.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(manifest, f)
        return Path(f.name)
