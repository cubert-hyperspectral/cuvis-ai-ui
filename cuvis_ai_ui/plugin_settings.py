"""Backward-compat shim -- real implementation moved to settings.plugins."""

# ruff: noqa: F401
from cuvis_ai_ui.settings.plugins import (
    build_manifest,
    get_default_plugin_entries,
    get_plugin_store_path,
    load_plugin_entries,
    merge_plugin_entries,
    reset_plugin_entries,
    save_plugin_entries,
    write_manifest_temp,
)
