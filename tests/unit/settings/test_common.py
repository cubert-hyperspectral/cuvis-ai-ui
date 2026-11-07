"""Tests for the shared config directory helper."""

from cuvis_ai_ui.settings.common import app_config_dir


def test_app_config_dir_stays_in_the_qt_test_folder():
    """Qt's test mode must be active so tests never touch the real per-user config dir."""
    path = app_config_dir()
    assert "qttest" in path.parts
