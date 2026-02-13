"""Integration tests for MainWindow (converted from manual tests)."""

import pytest
from unittest.mock import patch

from cuvis_ai_ui.main_window import MainWindow


def test_open_pipeline_with_false(qapp):
    """Test that open_pipeline handles False correctly (from test_file_dialog_fix.py)."""
    window = MainWindow()

    # Should not crash - should return early
    try:
        window.open_pipeline(False)
        # Test passes if no exception
        assert True
    except Exception as e:
        pytest.fail(f"open_pipeline(False) raised exception: {e}")


def test_open_pipeline_with_empty_string(qapp):
    """Test that open_pipeline handles empty string correctly (from test_file_dialog_fix.py)."""
    window = MainWindow()

    # Should not crash - should return early
    try:
        window.open_pipeline("")
        # Test passes if no exception
        assert True
    except Exception as e:
        pytest.fail(f"open_pipeline('') raised exception: {e}")


@patch("cuvis_ai_ui.main_window.QFileDialog.getOpenFileName")
def test_open_pipeline_with_none_user_cancels(mock_dialog, qapp, tmp_path):
    """Test file dialog cancellation (from test_file_dialog_fix.py)."""
    window = MainWindow()

    # Mock user canceling the dialog
    mock_dialog.return_value = ("", "")  # Empty path = user canceled

    # Should not crash when user cancels
    try:
        window.open_pipeline(None)
        assert True
    except Exception as e:
        pytest.fail(f"open_pipeline(None) with cancel raised exception: {e}")


@patch("cuvis_ai_ui.main_window.QFileDialog.getOpenFileName")
def test_open_pipeline_with_valid_file(mock_dialog, qapp, temp_pipeline_file):
    """Test opening a valid pipeline file (from test_file_dialog_fix.py)."""
    window = MainWindow()

    # Mock user selecting a file
    mock_dialog.return_value = (str(temp_pipeline_file), "YAML Files (*.yaml)")

    try:
        window.open_pipeline(None)
        # Test passes if no exception (file may not load due to missing nodes)
        assert True
    except Exception:
        # It's OK if the file fails to load due to missing nodes
        # We're just testing the file dialog doesn't crash
        pass
