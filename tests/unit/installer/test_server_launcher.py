"""The tray launcher runs in the server-venv, where cuvis_ai_ui is not installed,
so it keeps its own copy of the per-user data folder rule. These tests fail
when the two copies drift apart."""

import sys
from pathlib import Path

import pytest

from cuvis_ai_ui.server.manager import user_data_dir


def test_importing_the_launcher_has_no_side_effects(monkeypatch, tmp_path):
    """Output redirection and the log file belong to main(), so a test (or any
    importer) keeps its own stdout and writes no server.log."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    stdout, stderr = sys.stdout, sys.stderr

    from tests.unit.installer.conftest import load_installer_module

    load_installer_module("server_launcher")

    assert sys.stdout is stdout and sys.stderr is stderr
    assert not list(tmp_path.rglob("server.log"))


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_launcher_and_ui_agree_on_the_data_folder(launcher_module, monkeypatch, tmp_path, platform):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    assert launcher_module._user_data_dir() == user_data_dir()


def test_without_localappdata_both_fall_back_to_the_same_folder(
    launcher_module, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    assert launcher_module._user_data_dir() == user_data_dir()


def test_the_redirect_sends_output_to_the_server_log(launcher_module, monkeypatch, tmp_path):
    """main() calls this first: stdout and stderr go to server.log in the per-user
    data folder, and the tray menu reads its path."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    stdout, stderr = sys.stdout, sys.stderr
    try:
        launcher_module._redirect_output()
        log_file = sys.stdout
        assert sys.stderr is log_file
        print("hello from the server")
    finally:
        sys.stdout, sys.stderr = stdout, stderr
    log_file.close()

    assert launcher_module._LOG_PATH == user_data_dir() / "server.log"
    text = launcher_module._LOG_PATH.read_text(encoding="utf-8")
    assert "--- server start" in text
    assert "hello from the server" in text
