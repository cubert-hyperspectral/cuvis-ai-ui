"""Tests for server manager module."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import socket

import cuvis_ai_ui.server.manager as manager_module
from cuvis_ai_ui.server.manager import (
    SERVER_MODULE,
    ServerManager,
    _find_server_executable,
    _server_env,
    is_listening,
)


# ---------------------------------------------------------------------------
# _find_server_executable
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Per-user data folder in tmp, so no test touches the real one."""
    path = tmp_path / "data"
    monkeypatch.setattr(manager_module, "user_data_dir", lambda: path)
    return path


@pytest.fixture
def sibling_venv(tmp_path, monkeypatch):
    path = tmp_path / "core" / ".venv"
    monkeypatch.setattr(manager_module, "_sibling_core_venv", lambda: path)
    return path


@pytest.fixture
def core_importable(monkeypatch):
    def set_importable(importable):
        spec = object() if importable else None
        monkeypatch.setattr(manager_module.importlib.util, "find_spec", lambda name: spec)

    return set_importable


def _python_in(venv):
    python = venv / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("")
    return python


def test_find_prefers_the_per_user_server_venv(data_dir, sibling_venv):
    python = _python_in(data_dir / "server-venv")
    _python_in(sibling_venv)
    assert _find_server_executable() == [str(python), "-m", SERVER_MODULE]


def test_find_falls_back_to_the_sibling_core_venv(sibling_venv):
    python = _python_in(sibling_venv)
    assert _find_server_executable() == [str(python), "-m", SERVER_MODULE]


def test_find_uses_this_interpreter_when_it_imports_core(sibling_venv, core_importable):
    core_importable(True)
    assert _find_server_executable() == [sys.executable, "-m", SERVER_MODULE]


def test_find_returns_none_without_a_server_runtime(sibling_venv, core_importable):
    core_importable(False)
    assert _find_server_executable() is None


def test_frozen_build_only_uses_the_server_venv(sibling_venv, core_importable, monkeypatch):
    monkeypatch.setattr(manager_module.sys, "frozen", True, raising=False)
    _python_in(sibling_venv)
    core_importable(True)
    assert _find_server_executable() is None


def test_frozen_build_puts_bundled_tools_on_path(tmp_path, monkeypatch):
    app = tmp_path / "app"
    for tool in ("ffmpeg", "graphviz"):
        (app / tool / "bin").mkdir(parents=True)
    monkeypatch.setattr(manager_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(manager_module.sys, "executable", str(app / "cuvis-ui.exe"))
    existing = str(tmp_path / "existing")
    monkeypatch.setenv("PATH", existing)

    env = _server_env(50052)

    assert env["GRPC_PORT"] == "50052"
    assert env["PATH"].split(os.pathsep) == [
        str(app / "ffmpeg" / "bin"),
        str(app / "graphviz" / "bin"),
        existing,
    ]


def test_dev_run_keeps_path(monkeypatch):
    monkeypatch.setenv("PATH", "C:/existing")
    assert _server_env(50051)["PATH"] == "C:/existing"


# ---------------------------------------------------------------------------
# CUVIS: a UI started before (or by) the SDK install has none in its environment
# ---------------------------------------------------------------------------


@pytest.fixture
def machine_cuvis(monkeypatch):
    """Windows with a fake machine environment; returns the dict to fill."""
    machine: dict[str, str] = {}
    monkeypatch.setattr(manager_module.sys, "platform", "win32")
    monkeypatch.setattr(manager_module, "_machine_env_value", machine.get)
    monkeypatch.delenv("CUVIS", raising=False)
    return machine


def test_server_gets_cuvis_from_the_machine_environment(machine_cuvis):
    machine_cuvis["CUVIS"] = r"C:\Program Files\Cuvis\bin"
    assert _server_env(50051)["CUVIS"] == r"C:\Program Files\Cuvis\bin"


@pytest.fixture
def sdk_folder(tmp_path):
    """Make a CUVIS folder, with or without the SDK library in it."""

    def make(name: str, library: bool) -> str:
        folder = tmp_path / name
        folder.mkdir()
        if library:
            (folder / "cuvis.dll").write_bytes(b"")
        return str(folder)

    return make


def test_cuvis_already_in_the_environment_wins(machine_cuvis, monkeypatch, sdk_folder):
    machine = machine_cuvis["CUVIS"] = sdk_folder("machine", library=True)
    current = sdk_folder("dev", library=True)
    monkeypatch.setenv("CUVIS", current)
    warn = Mock()
    monkeypatch.setattr(manager_module.logger, "warning", warn)

    assert _server_env(50051)["CUVIS"] == current
    warn.assert_called_once()
    assert current in warn.call_args.args[0]
    assert machine in warn.call_args.args[0]


def test_inherited_cuvis_without_the_library_gives_way(machine_cuvis, monkeypatch, sdk_folder):
    machine = machine_cuvis["CUVIS"] = sdk_folder("machine", library=True)
    stale = sdk_folder("stale", library=False)
    monkeypatch.setenv("CUVIS", stale)
    warn = Mock()
    monkeypatch.setattr(manager_module.logger, "warning", warn)

    assert _server_env(50051)["CUVIS"] == machine
    warn.assert_called_once()
    assert stale in warn.call_args.args[0]
    assert "cuvis.dll" in warn.call_args.args[0]


def test_inherited_cuvis_stays_when_neither_has_the_library(machine_cuvis, monkeypatch, sdk_folder):
    machine_cuvis["CUVIS"] = sdk_folder("machine", library=False)
    current = sdk_folder("dev", library=False)
    monkeypatch.setenv("CUVIS", current)
    monkeypatch.setattr(manager_module.logger, "warning", Mock())

    assert _server_env(50051)["CUVIS"] == current


def test_unreadable_inherited_cuvis_does_not_stop_the_server(
    machine_cuvis, monkeypatch, sdk_folder
):
    machine = machine_cuvis["CUVIS"] = sdk_folder("machine", library=True)
    locked = sdk_folder("locked", library=False)
    monkeypatch.setenv("CUVIS", locked)
    real_stat = os.stat

    def stat(path, *args, **kwargs):
        if str(path).startswith(locked):
            raise PermissionError(13, "Access is denied", str(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(manager_module.logger, "warning", Mock())

    assert _server_env(50051)["CUVIS"] == machine


def test_matching_cuvis_logs_nothing(machine_cuvis, monkeypatch):
    machine_cuvis["CUVIS"] = r"C:\Program Files\Cuvis\bin"
    monkeypatch.setenv("CUVIS", r"C:\Program Files\Cuvis\bin")
    warn = Mock()
    monkeypatch.setattr(manager_module.logger, "warning", warn)

    assert _server_env(50051)["CUVIS"] == r"C:\Program Files\Cuvis\bin"
    warn.assert_not_called()


def test_empty_cuvis_counts_as_missing(machine_cuvis, monkeypatch):
    machine_cuvis["CUVIS"] = r"C:\Program Files\Cuvis\bin"
    monkeypatch.setenv("CUVIS", "")
    assert _server_env(50051)["CUVIS"] == r"C:\Program Files\Cuvis\bin"


def test_no_machine_cuvis_leaves_it_unset(machine_cuvis):
    assert "CUVIS" not in _server_env(50051)


def test_other_platforms_do_not_read_the_machine_environment(monkeypatch):
    lookup = Mock(return_value="/opt/cuvis")
    monkeypatch.setattr(manager_module.sys, "platform", "linux")
    monkeypatch.setattr(manager_module, "_machine_env_value", lookup)
    monkeypatch.delenv("CUVIS", raising=False)

    assert "CUVIS" not in _server_env(50051)
    lookup.assert_not_called()


class _FakeWinreg:
    """The bits of winreg _machine_env_value uses."""

    HKEY_LOCAL_MACHINE = "HKLM"
    REG_SZ = 1
    REG_EXPAND_SZ = 2

    def __init__(self, values, opened=None):
        self.values = values
        self.opened = opened if opened is not None else []

    def OpenKey(self, root, path):  # noqa: N802 (winreg's name)
        self.opened.append((root, path))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name]

    @staticmethod
    def ExpandEnvironmentStrings(value):  # noqa: N802
        return value.replace("%ProgramFiles%", r"C:\Program Files")


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ((r"C:\Program Files\Cuvis\bin", _FakeWinreg.REG_SZ), r"C:\Program Files\Cuvis\bin"),
        ((r"%ProgramFiles%\Cuvis\bin", _FakeWinreg.REG_EXPAND_SZ), r"C:\Program Files\Cuvis\bin"),
    ],
    ids=["plain", "expand"],
)
def test_machine_env_value_reads_the_session_manager_key(monkeypatch, stored, expected):
    fake = _FakeWinreg({"CUVIS": stored})
    monkeypatch.setitem(sys.modules, "winreg", fake)

    assert manager_module._machine_env_value("CUVIS") == expected
    assert fake.opened == [
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
    ]


def test_machine_env_value_is_none_when_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", _FakeWinreg({}))
    assert manager_module._machine_env_value("CUVIS") is None


# ---------------------------------------------------------------------------
# is_listening
# ---------------------------------------------------------------------------


def test_is_listening_true_against_a_real_listening_socket():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        assert is_listening("localhost", port)
    finally:
        server.close()


def test_is_listening_false_against_a_closed_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("localhost", 0))
    port = probe.getsockname()[1]
    probe.close()  # Nothing listens on this port once we release it.

    assert not is_listening("localhost", port, timeout=0.2)


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


@patch("cuvis_ai_ui.server.manager._find_server_executable", return_value=None)
def test_start_without_a_server_runtime_explains(mock_find_exe):
    manager = ServerManager()
    manager.start()
    assert manager.process is None
    assert "No cuvis-ai-core server found" in manager.last_error


@patch("cuvis_ai_ui.server.manager.subprocess.Popen")
@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_start_handles_a_log_that_cannot_be_opened(mock_find_exe, mock_popen, data_dir):
    mock_find_exe.return_value = ["python", "-m", SERVER_MODULE]

    manager = ServerManager()
    data_dir.mkdir(parents=True)
    # A directory where the log file should be makes the open() call fail.
    manager.log_path.mkdir()

    manager.start()

    mock_popen.assert_not_called()
    assert manager.process is None
    assert manager.is_running() is False
    assert str(manager.log_path) in manager.last_error


@patch("cuvis_ai_ui.server.manager.subprocess.Popen")
@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_start_sends_server_output_to_the_log(mock_find_exe, mock_popen, data_dir):
    mock_find_exe.return_value = ["python", "-m", SERVER_MODULE]
    mock_popen.return_value = Mock(pid=1, poll=Mock(return_value=None))

    manager = ServerManager()
    manager.start()

    kwargs = mock_popen.call_args.kwargs
    assert kwargs["stdout"] is not subprocess.PIPE
    assert Path(kwargs["stdout"].name) == data_dir / "server.log"
    assert kwargs["stderr"] is subprocess.STDOUT
    assert manager.log_path == data_dir / "server.log"
    assert "server start" in manager.log_path.read_text(encoding="utf-8")


@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_a_chatty_server_never_blocks_on_its_output(mock_find_exe):
    mock_find_exe.return_value = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('x' * 1_000_000 + chr(10) + 'last line' + chr(10))",
    ]
    manager = ServerManager()
    manager.start()

    assert manager.process.wait(timeout=30) == 0
    assert manager.log_tail(max_lines=1) == "last line"


def test_log_tail_only_shows_this_run(data_dir):
    manager = ServerManager()
    data_dir.mkdir()
    manager.log_path.write_bytes(b"old run\n")
    manager._log_offset = manager.log_path.stat().st_size
    with open(manager.log_path, "ab") as log:
        log.write(b"crash output\n")
    assert manager.log_tail() == "crash output"


def test_log_tail_without_a_log():
    assert ServerManager().log_tail() == ""


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
    manager._process = mock_process
    manager.log_path.parent.mkdir(parents=True)
    manager.log_path.write_bytes(b"crash output\n")

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
    mock_ch.close.assert_called_once()


def _running_manager():
    manager = ServerManager()
    process = Mock()
    process.poll.return_value = None
    manager._process = process
    return manager


@patch("cuvis_ai_ui.server.manager.grpc.channel_ready_future")
@patch("cuvis_ai_ui.server.manager.grpc.insecure_channel")
def test_wait_ready_stops_at_the_next_poll_once_the_event_is_set(mock_channel, mock_ready_future):
    """A cancelled wait ends at the next poll, closes the channel it opened and
    reports no error: the user stopped waiting, nothing failed."""
    import threading

    import grpc

    from cuvis_ai_ui.grpc.client import OperationCancelled

    stop = threading.Event()
    channels = [Mock(), Mock()]
    mock_channel.side_effect = channels

    def not_ready_yet(timeout):
        stop.set()
        raise grpc.FutureTimeoutError()

    mock_ready_future.return_value.result.side_effect = not_ready_yet
    manager = _running_manager()

    with pytest.raises(OperationCancelled):
        manager.wait_ready(timeout=60.0, stop=stop)

    assert mock_channel.call_count == 1
    channels[0].close.assert_called_once()
    assert manager.last_error == ""


@patch("cuvis_ai_ui.server.manager.grpc.channel_ready_future")
@patch("cuvis_ai_ui.server.manager.grpc.insecure_channel")
@patch("cuvis_ai_ui.server.manager.time.monotonic")
def test_a_cancel_during_the_last_poll_is_a_cancel_not_a_timeout(
    mock_monotonic, mock_channel, mock_ready_future
):
    """The last poll can run past the deadline while the user presses Cancel;
    that still ends as a cancel, so the caller does not act on a timeout."""
    import threading

    import grpc

    from cuvis_ai_ui.grpc.client import OperationCancelled

    stop = threading.Event()
    mock_monotonic.side_effect = [0, 0, 100]
    mock_ch = Mock()
    mock_channel.return_value = mock_ch

    def cancelled_while_waiting(timeout):
        stop.set()
        raise grpc.FutureTimeoutError()

    mock_ready_future.return_value.result.side_effect = cancelled_while_waiting
    manager = _running_manager()

    with pytest.raises(OperationCancelled):
        manager.wait_ready(timeout=5.0, stop=stop)
    mock_ch.close.assert_called_once()
    assert manager.last_error == ""


@patch("cuvis_ai_ui.server.manager.time.sleep")
@patch("cuvis_ai_ui.server.manager.grpc.channel_ready_future")
@patch("cuvis_ai_ui.server.manager.grpc.insecure_channel")
@patch("cuvis_ai_ui.server.manager.time.monotonic")
def test_wait_ready_closes_the_channel_when_the_check_raises(
    mock_monotonic, mock_channel, mock_ready_future, mock_sleep
):
    mock_monotonic.side_effect = [0, 0, 100]
    mock_ch = Mock()
    mock_channel.return_value = mock_ch
    mock_ready_future.return_value.result.side_effect = RuntimeError("socket gone")

    assert not _running_manager().wait_ready(timeout=5.0)
    mock_ch.close.assert_called_once()


@patch("cuvis_ai_ui.server.manager.grpc.channel_ready_future")
@patch("cuvis_ai_ui.server.manager.grpc.insecure_channel")
def test_wait_ready_waits_out_a_failed_check_on_the_stop_event(mock_channel, mock_ready_future):
    """After a failed check the pause between polls is the stop event's wait,
    so Cancel ends it at once instead of after the poll interval."""
    import threading

    from cuvis_ai_ui.grpc.client import OperationCancelled

    stop = threading.Event()
    mock_channel.return_value = Mock()

    def broken(timeout):
        stop.set()
        raise RuntimeError("socket gone")

    mock_ready_future.return_value.result.side_effect = broken

    with patch("cuvis_ai_ui.server.manager.time.sleep") as mock_sleep:
        with pytest.raises(OperationCancelled):
            _running_manager().wait_ready(timeout=60.0, poll_interval=30.0, stop=stop)
    mock_sleep.assert_not_called()


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


class _FullDiskLog:
    """A log file whose writes fail as on a full disk."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, data):
        raise OSError(28, "No space left on device")

    def close(self):
        pass


@patch("cuvis_ai_ui.server.manager.subprocess.Popen")
@patch("cuvis_ai_ui.server.manager._find_server_executable")
def test_start_handles_a_log_that_cannot_be_written(mock_find_exe, mock_popen, data_dir):
    mock_find_exe.return_value = ["python", "-m", SERVER_MODULE]
    manager = ServerManager()

    with patch("cuvis_ai_ui.server.manager.open", create=True, return_value=_FullDiskLog()):
        manager.start()

    mock_popen.assert_not_called()
    assert manager.process is None
    assert "No space left on device" in manager.last_error
