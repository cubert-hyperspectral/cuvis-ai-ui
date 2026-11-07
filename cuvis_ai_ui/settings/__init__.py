"""Application settings persistence (connection, plugins)."""

from cuvis_ai_ui.settings.common import APP_NAME, ORG_NAME, app_config_dir, set_app_identity
from cuvis_ai_ui.settings.connection import (
    get_default_connection_settings,
    load_connection_settings,
    save_connection_settings,
)
from cuvis_ai_ui.settings.plugins import (
    build_manifest,
    collect_plugin_entries,
    get_catalog_dir,
    get_default_plugin_entries,
    get_plugin_store_path,
    get_user_plugins_dir,
    is_bundled_plugin,
    load_plugin_entries,
    load_plugin_entries_from_directory,
    merge_plugin_entries,
    reset_plugin_entries,
    save_plugin_entries,
    write_manifest_temp,
)

__all__ = [
    "APP_NAME",
    "ORG_NAME",
    "app_config_dir",
    "set_app_identity",
    # Connection
    "get_default_connection_settings",
    "load_connection_settings",
    "save_connection_settings",
    # Plugins
    "build_manifest",
    "collect_plugin_entries",
    "get_catalog_dir",
    "get_default_plugin_entries",
    "get_plugin_store_path",
    "get_user_plugins_dir",
    "is_bundled_plugin",
    "load_plugin_entries",
    "load_plugin_entries_from_directory",
    "merge_plugin_entries",
    "reset_plugin_entries",
    "save_plugin_entries",
    "write_manifest_temp",
]
