"""Manage the local cuvis-ai-core gRPC server subprocess."""

from __future__ import annotations

import atexit
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import grpc
from loguru import logger

SERVER_MODULE = "cuvis_ai_core.grpc.production_server"


def user_data_dir() -> Path:
    """Per-user folder the installer shares with the UI (server-venv, server.log)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Cubert GmbH" / "Cuvis.AI UI"
    return Path.home() / ".config" / "cuvis-ai-ui"


def _venv_python(venv: Path) -> Path | None:
    for python in (venv / "Scripts" / "python.exe", venv / "bin" / "python"):
        if python.exists():
            return python
    return None


def _sibling_core_venv() -> Path:
    """The ``.venv`` of a cuvis-ai-core checkout next to this one.

    ``<repos>/cuvis-ai-ui/<checkout>/cuvis_ai_ui/server/manager.py`` maps to
    ``<repos>/cuvis-ai-core/cuvis-ai-core/.venv``.
    """
    repos_dir = Path(__file__).resolve().parents[4]
    return repos_dir / "cuvis-ai-core" / "cuvis-ai-core" / ".venv"


def _find_server_executable() -> list[str] | None:
    """Return the command that starts the gRPC server, or None if there is none.

    Order: the per-user server-venv the installer creates, then (outside a
    frozen build) a sibling cuvis-ai-core checkout's ``.venv``, then this
    interpreter when it can import ``cuvis_ai_core``.
    """
    candidates = [_venv_python(user_data_dir() / "server-venv")]
    if not getattr(sys, "frozen", False):
        candidates.append(_venv_python(_sibling_core_venv()))
        if importlib.util.find_spec("cuvis_ai_core") is not None:
            candidates.append(Path(sys.executable))
    for python in candidates:
        if python is not None:
            logger.debug(f"Server interpreter: {python}")
            return [str(python), "-m", SERVER_MODULE]
    return None


def _server_env(port: int) -> dict[str, str]:
    """Environment for the server; a frozen build puts its bundled tools on PATH."""
    env = {**os.environ, "GRPC_PORT": str(port), "LOG_FORMAT": "text"}
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        tools = [app_dir / name / "bin" for name in ("ffmpeg", "graphviz")]
        prefix = [str(t) for t in tools if t.is_dir()]
        if prefix:
            env["PATH"] = os.pathsep.join([*prefix, env.get("PATH", "")])
    return env


class ServerManager:
    """Start / stop / health-check the local cuvis-ai-core gRPC server."""

    def __init__(self, port: int = 50051) -> None:
        self._port = port
        self._process: subprocess.Popen | None = None
        self._last_error: str = ""
        self._log_path = user_data_dir() / "server.log"
        self._log_offset = 0
        # Register cleanup so the server is stopped even on unclean exit.
        # Use _atexit_stop (no logging) because output streams may already
        # be closed when atexit callbacks run (e.g. pytest-cov closes stderr).
        atexit.register(self._atexit_stop)

    @property
    def port(self) -> int:
        return self._port

    @property
    def process(self) -> subprocess.Popen | None:
        return self._process

    @property
    def last_error(self) -> str:
        """Last error message from the server process."""
        return self._last_error

    @property
    def log_path(self) -> Path:
        """File the server's output is appended to."""
        return self._log_path

    def is_running(self) -> bool:
        """Return True if the server subprocess is alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def start(self) -> None:
        """Spawn the server subprocess (no-op if already running).

        The server's output is appended to :attr:`log_path`. Returns with
        :attr:`last_error` set when no server runtime is found; the UI still
        works without a local server.
        """
        if self.is_running():
            logger.info(f"Server already running (pid={self._process.pid})")
            return

        cmd = _find_server_executable()
        if cmd is None:
            self._last_error = (
                "No cuvis-ai-core server found. Run 'Setup local server' from the "
                "Cuvis.AI UI start menu folder, or create the .venv of a cuvis-ai-core "
                "checkout next to this one."
            )
            logger.warning(self._last_error)
            return

        logger.info(f"Starting local gRPC server: {' '.join(cmd)} (port {self._port})")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "ab") as log:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"\n--- server start {stamp}: {' '.join(cmd)} ---\n".encode())
            log.flush()
            self._log_offset = log.tell()
            try:
                self._process = subprocess.Popen(
                    cmd,
                    env=_server_env(self._port),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
            except OSError as e:
                self._last_error = f"Could not start the server ({' '.join(cmd)}): {e}"
                logger.warning(self._last_error)
                self._process = None
                return
        logger.info(f"Server started (pid={self._process.pid}), log: {self._log_path}")

    def log_tail(self, max_lines: int = 40) -> str:
        """Return the last lines the current server run wrote to its log."""
        try:
            with open(self._log_path, "rb") as log:
                log.seek(self._log_offset)
                text = log.read().decode("utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(text.splitlines()[-max_lines:])

    def wait_ready(self, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
        """Block until the server responds to a gRPC health check.

        Returns True if the server became ready, False on timeout.
        """
        if self._process is None:
            return False

        target = f"localhost:{self._port}"
        deadline = time.monotonic() + timeout
        logger.info(f"Waiting for server at {target} (timeout={timeout:.0f}s)...")

        while time.monotonic() < deadline:
            if not self.is_running():
                self._last_error = self.log_tail()
                logger.warning(
                    f"Server process exited before becoming ready. Output:\n{self._last_error}"
                )
                return False
            try:
                channel = grpc.insecure_channel(target)
                grpc.channel_ready_future(channel).result(timeout=poll_interval)
                channel.close()
                logger.info(f"Server is ready at {target}")
                return True
            except grpc.FutureTimeoutError:
                pass
            except Exception:
                time.sleep(poll_interval)

        logger.warning(f"Server did not become ready within {timeout:.0f}s")
        self._last_error = (
            f"Timeout after {timeout}s waiting for server at {target}. Server log: {self._log_path}"
        )
        return False

    def _atexit_stop(self) -> None:
        """Terminate the server at exit without logging.

        Output streams (stderr) may already be closed when atexit callbacks
        run, which causes loguru to emit "I/O operation on closed file"
        errors.  This method skips all logging.
        """
        if self._process is None or self._process.poll() is not None:
            self._process = None
            return

        self._process.terminate()
        try:
            self._process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        self._process = None

    def stop(self, grace: float = 5.0) -> None:
        """Gracefully terminate the server subprocess."""
        if self._process is None or self._process.poll() is not None:
            self._process = None
            return

        pid = self._process.pid
        logger.info(f"Stopping server (pid={pid})...")

        self._process.terminate()
        try:
            self._process.wait(timeout=grace)
            logger.info(f"Server stopped gracefully (pid={pid})")
        except subprocess.TimeoutExpired:
            logger.warning(f"Server did not stop in {grace:.0f}s, killing (pid={pid})")
            self._process.kill()
            self._process.wait(timeout=5)

        self._process = None
