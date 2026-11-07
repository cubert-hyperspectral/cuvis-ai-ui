"""Shared config directory helper."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths

APP_NAME = "Cuvis.AI UI"
ORG_NAME = "Cubert GmbH"


def set_app_identity() -> None:
    """Set the application and organization name Qt uses to resolve config paths.

    This has to run before any call to ``app_config_dir`` (directly, or via a
    settings loader), including before a QApplication exists, since
    ``QStandardPaths`` keys the config folder off these names. A ``--test``
    run and the GUI must resolve the same folder, so both call this first.
    """
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName(ORG_NAME)


def app_config_dir() -> Path:
    """Return the platform-specific application config directory."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if location:
        return Path(location)
    return Path.home() / ".config" / "cuvis_ai_ui"
