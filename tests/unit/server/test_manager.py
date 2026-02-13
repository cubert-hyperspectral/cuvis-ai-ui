"""Tests for server manager module."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch


from cuvis_ai_ui.server.manager import ServerManager, _find_server_executable


# ---------------------------------------------------------------------------
# _find_server_executable
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.server.manager.sys")
def test_find_server_executable_frozen(mock_sys):
    """Test finding server executable in frozen (PyInstaller) build."""
    mock_sys.frozen = True
    mock_sys.executable = "C:/app/cuvis-ui.exe"
    mock_sys.platform = "win32"

    with patch.object(Path, "exists", return_value=True):
        cmd = _find_server_executable()
        assert "cuvis-server.exe" in cmd[0]


@patch("cuvis_ai_ui.server.manager.sys")
def test_find_server_executable_frozen_fallback(mock_sys):
    """Test fallback when server exe not found in frozen build."""
    mock_sys.frozen = True
    mock_sys.executable = "C:/app/cuvis-ui.exe"

    with patch.object(Path, "exists", return_value=False):
        cmd = _find_server_executable()
        assert cmd == ["cuvis-server"]


def test_find_server_executable_dev_mode_fallback():
    """Test fallback to current Python in dev mode."""
    # In dev mode, if cuvis-ai-core venv doesn't exist, falls back to sys.executable
    cmd = _find_server_executable()
    assert len(cmd) >= 1
    # Either finds core venv or falls back to sys.executable
    assert cmd[-1] == "cuvis_ai_core.grpc.production_server" or "python" in cmd[0].lower()


# ---------------------------------------------------------------------------
# ServerManager - Initialization
# ---------------------------------------------------------------------------


def test_server_manager_init():
    """Test ServerManager initialization."""
    manager = ServerManager(port=50051)

    assert manager.port == 50051
    assert manager.process is None
    assert manager.last_error == ""
    assert not manager.is_running()


def test_server_manager_custom_port():
    """Test ServerManager with custom port."""
    manager = ServerManager(port=9999)
    assert manager.port == 9999


# ---------------------------------------------------------------------------
# ServerManager.is_running
# ---------------------------------------------------------------------------


def test_is_running_no_process():
    """Test is_running returns False when no process."""
    manager = ServerManager()
    assert not manager.is_running()


def test_is_running_alive_process():
    """Test is_running returns True when process is alive."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = None  # Still running
    manager._process = mock_process

    assert manager.is_running()


def test_is_running_dead_process():
    """Test is_running returns False when process has exited."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = 0  # Exited
    manager._process = mock_process

    assert not manager.is_running()


# ---------------------------------------------------------------------------
# ServerManager.start
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.server.manager.subprocess.Popen")
@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_start_spawns_process(mock_find_exe, mock_popen):
    """Test start spawns a subprocess."""
    mock_find_exe.return_value = ["python", "-m", "cuvis_ai_core.grpc.production_server"]
    mock_process = Mock()
    mock_process.pid = 12345
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process

    manager = ServerManager()
    manager.start()

    mock_popen.assert_called_once()
    assert manager._process is mock_process


@patch("cuvis_ai_ui.server.manager.subprocess.Popen")
@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_start_already_running_is_noop(mock_find_exe, mock_popen):
    """Test start does nothing if server is already running."""
    mock_find_exe.return_value = ["python", "-m", "server"]
    mock_process = Mock()
    mock_process.poll.return_value = None  # Still running
    mock_process.pid = 123

    manager = ServerManager()
    manager._process = mock_process

    manager.start()

    mock_popen.assert_not_called()


@patch("cuvis_ai_ui.server.manager.subprocess.Popen")
@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_start_handles_file_not_found(mock_find_exe, mock_popen):
    """Test start handles FileNotFoundError gracefully."""
    mock_find_exe.return_value = ["nonexistent-server"]
    mock_popen.side_effect = FileNotFoundError("Not found")

    manager = ServerManager()
    manager.start()

    assert manager._process is None


# ---------------------------------------------------------------------------
# ServerManager.get_output
# ---------------------------------------------------------------------------


def test_get_output_no_process():
    """Test get_output returns empty string when no process."""
    manager = ServerManager()
    assert manager.get_output() == ""


def test_get_output_no_stdout():
    """Test get_output returns empty string when stdout is None."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.stdout = None
    manager._process = mock_process

    assert manager.get_output() == ""


def test_get_output_exited_process():
    """Test get_output reads remaining output from exited process."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = 1  # Exited
    mock_process.stdout = Mock()
    mock_process.stdout.fileno.side_effect = OSError("bad fd")
    mock_process.stdout.read.return_value = b"Server output"
    manager._process = mock_process

    output = manager.get_output()
    assert output == "Server output"


# ---------------------------------------------------------------------------
# ServerManager.wait_ready
# ---------------------------------------------------------------------------


def test_wait_ready_no_process():
    """Test wait_ready returns False when no process."""
    manager = ServerManager()
    assert not manager.wait_ready(timeout=0.1)


@patch("cuvis_ai_ui.server.manager.grpc.channel_ready_future")
@patch("cuvis_ai_ui.server.manager.grpc.insecure_channel")
def test_wait_ready_success(mock_channel, mock_ready_future):
    """Test wait_ready returns True when server becomes ready."""
    mock_ch = Mock()
    mock_channel.return_value = mock_ch

    mock_future = Mock()
    mock_future.result.return_value = None  # Ready
    mock_ready_future.return_value = mock_future

    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = None  # Still running
    manager._process = mock_process

    assert manager.wait_ready(timeout=5.0)
    mock_ch.close.assert_called_once()


@patch("cuvis_ai_ui.server.manager.time.monotonic")
def test_wait_ready_process_exits(mock_monotonic):
    """Test wait_ready returns False when process exits."""
    # Simulate time progression
    mock_monotonic.side_effect = [0, 0, 1]

    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = 1  # Exited
    mock_process.stdout = Mock()
    mock_process.stdout.fileno.side_effect = OSError()
    mock_process.stdout.read.return_value = b"crash output"
    manager._process = mock_process

    result = manager.wait_ready(timeout=5.0)
    assert not result
    assert "crash output" in manager.last_error


@patch("cuvis_ai_ui.server.manager.grpc.channel_ready_future")
@patch("cuvis_ai_ui.server.manager.grpc.insecure_channel")
@patch("cuvis_ai_ui.server.manager.time.monotonic")
def test_wait_ready_timeout(mock_monotonic, mock_channel, mock_ready_future):
    """Test wait_ready returns False on timeout."""
    import grpc

    # Simulate time that exceeds timeout
    mock_monotonic.side_effect = [0, 0, 100]

    mock_ch = Mock()
    mock_channel.return_value = mock_ch

    mock_future = Mock()
    mock_future.result.side_effect = grpc.FutureTimeoutError()
    mock_ready_future.return_value = mock_future

    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = None  # Still running
    manager._process = mock_process

    result = manager.wait_ready(timeout=5.0)
    assert not result
    assert "Timeout" in manager.last_error


# ---------------------------------------------------------------------------
# ServerManager.stop
# ---------------------------------------------------------------------------


def test_stop_no_process():
    """Test stop does nothing when no process."""
    manager = ServerManager()
    manager.stop()
    assert manager._process is None


def test_stop_already_exited():
    """Test stop handles already-exited process."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = 0  # Already exited
    manager._process = mock_process

    manager.stop()
    assert manager._process is None


def test_stop_graceful():
    """Test stop terminates process gracefully."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = None  # Running
    mock_process.pid = 123
    mock_process.wait.return_value = None
    manager._process = mock_process

    manager.stop()

    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once()
    assert manager._process is None


def test_stop_kills_on_timeout():
    """Test stop kills process if graceful shutdown times out."""
    manager = ServerManager()
    mock_process = Mock()
    mock_process.poll.return_value = None  # Running
    mock_process.pid = 123
    mock_process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]
    manager._process = mock_process

    manager.stop(grace=0.1)

    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()
    assert manager._process is None
