"""Application settings persistence (connection, plugins)."""

from cuvis_ai_ui.settings.common import app_config_dir
from cuvis_ai_ui.settings.connection import (
    get_default_connection_settings,
    load_connection_settings,
    save_connection_settings,
)
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

__all__ = [
    "app_config_dir",
    # Connection
    "get_default_connection_settings",
    "load_connection_settings",
    "save_connection_settings",
    # Plugins
    "build_manifest",
    "get_default_plugin_entries",
    "get_plugin_store_path",
    "load_plugin_entries",
    "merge_plugin_entries",
    "reset_plugin_entries",
    "save_plugin_entries",
    "write_manifest_temp",
]
