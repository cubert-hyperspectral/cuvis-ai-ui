"""Shared config directory helper."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths


def app_config_dir() -> Path:
    """Return the platform-specific application config directory."""
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    if location:
        return Path(location)
    return Path.home() / ".config" / "cuvis_ai_ui"
