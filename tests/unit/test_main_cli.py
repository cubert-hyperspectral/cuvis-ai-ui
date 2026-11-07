"""Tests for the cuvis-ui CLI entry point in cuvis_ai_ui.main."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner
from PySide6.QtCore import QCoreApplication

from cuvis_ai_ui import main as main_module
from cuvis_ai_ui.settings import APP_NAME, ORG_NAME, get_default_connection_settings


@pytest.fixture
def restore_app_identity():
    """Restore whatever application/organization name was set before the test."""
    previous_app_name = QCoreApplication.applicationName()
    previous_org_name = QCoreApplication.organizationName()
    yield
    QCoreApplication.setApplicationName(previous_app_name)
    QCoreApplication.setOrganizationName(previous_org_name)


def test_test_mode_reads_connection_settings_after_app_identity_is_set(restore_app_identity):
    """--test must read connection.json only after the app/org name are set.

    Reading it earlier makes Qt resolve a different, unnamed config folder,
    so the UI and a --test run disagree on where connection.json lives.
    """
    QCoreApplication.setApplicationName("")
    QCoreApplication.setOrganizationName("")

    recorded = {}

    def fake_load_connection_settings():
        recorded["app_name"] = QCoreApplication.applicationName()
        recorded["org_name"] = QCoreApplication.organizationName()
        return get_default_connection_settings()

    with (
        patch.object(
            main_module, "load_connection_settings", side_effect=fake_load_connection_settings
        ),
        patch.object(main_module, "_run_connection_test") as mock_run_test,
    ):
        runner = CliRunner()
        result = runner.invoke(main_module.main, ["--test"])

    assert result.exit_code == 0, result.output
    mock_run_test.assert_called_once()
    assert recorded["app_name"] == APP_NAME
    assert recorded["org_name"] == ORG_NAME


def test_connection_command_sets_app_identity_first(restore_app_identity):
    """cuvis-ui-test registers the app's plugin folders, so it needs the app's names too."""
    QCoreApplication.setApplicationName("")
    QCoreApplication.setOrganizationName("")

    recorded = {}

    def fake_run_connection_test(*args, **kwargs):
        recorded["app_name"] = QCoreApplication.applicationName()
        recorded["org_name"] = QCoreApplication.organizationName()

    with patch.object(main_module, "_run_connection_test", side_effect=fake_run_connection_test):
        result = CliRunner().invoke(main_module.test_connection, [])

    assert result.exit_code == 0, result.output
    assert recorded == {"app_name": APP_NAME, "org_name": ORG_NAME}
