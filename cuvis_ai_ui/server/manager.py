"""Manage the local cuvis-ai-core gRPC server subprocess."""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
import time
from pathlib import Path

import grpc
from loguru import logger


def _find_server_executable() -> list[str]:
    """Return the command to start the gRPC server.

    In a PyInstaller frozen build the server executable lives next to the UI
    executable at ``<app>/server/cuvis-server.exe``.  During development we
    look for the cuvis-ai-core project's own venv Python, since cuvis_ai_core
    is typically not installed in the UI venv.
    """
    if getattr(sys, "frozen", False):
        # Frozen build — look for the server exe next to this exe
        app_dir = Path(sys.executable).parent
        server_exe = app_dir / "server" / "cuvis-server.exe"
        if server_exe.exists():
            return [str(server_exe)]
        # Fallback: maybe the server is on PATH
        return ["cuvis-server"]

    # Development mode — try to find cuvis-ai-core's own venv
    # __file__ is <ui-project>/cuvis_ai_ui/server/manager.py
    # ui_project is <repos>/cuvis-ai-ui/cuvis-ai-ui
    # core is at   <repos>/cuvis-ai-core/cuvis-ai-core
    ui_project = Path(__file__).resolve().parent.parent.parent
    repos_dir = ui_project.parent.parent  # up to <repos>
    core_candidates = [
        repos_dir / "cuvis-ai-core" / "cuvis-ai-core",
    ]
    for core_root in core_candidates:
        core_root = core_root.resolve()
        core_python = core_root / ".venv" / "Scripts" / "python.exe"
        if not core_python.exists():
            # Linux/macOS
            core_python = core_root / ".venv" / "bin" / "python"
        if core_python.exists():
            logger.debug("Found cuvis-ai-core venv at %s", core_python)
            return [str(core_python), "-m", "cuvis_ai_core.grpc.production_server"]

    # Fallback: try current Python (works if cuvis_ai_core is installed in UI venv)
    return [sys.executable, "-m", "cuvis_ai_core.grpc.production_server"]


class ServerManager:
    """Start / stop / health-check the local cuvis-ai-core gRPC server."""

    def __init__(self, port: int = 50051) -> None:
        self._port = port
        self._process: subprocess.Popen | None = None
        self._last_error: str = ""
        # Register cleanup so the server is stopped even on unclean exit
        atexit.register(self.stop)

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

    def is_running(self) -> bool:
        """Return True if the server subprocess is alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def start(self) -> None:
        """Spawn the server subprocess (no-op if already running).

        Returns silently if the server executable cannot be found — the UI
        can still operate without a local server.
        """
        if self.is_running():
            logger.info("Server already running (pid=%s)", self._process.pid)
            return

        cmd = _find_server_executable()
        env = {**os.environ, "GRPC_PORT": str(self._port), "LOG_FORMAT": "text"}

        logger.info("Starting local gRPC server: %s (port %s)", " ".join(cmd), self._port)
        try:
            self._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except FileNotFoundError:
            logger.warning(
                "Server executable not found: %s. "
                "Make sure cuvis-ai-core is installed or its venv exists.",
                " ".join(cmd),
            )
            self._process = None
            return
        logger.info("Server started (pid=%s)", self._process.pid)

    def get_output(self) -> str:
        """Read any available stdout/stderr from the server process."""
        if self._process is None or self._process.stdout is None:
            return ""
        try:
            # Non-blocking read of whatever is available
            import msvcrt
            import ctypes
            handle = msvcrt.get_osfhandle(self._process.stdout.fileno())
            avail = ctypes.c_ulong(0)
            ctypes.windll.kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(avail), None,
            )
            if avail.value > 0:
                return self._process.stdout.read(avail.value).decode("utf-8", errors="replace")
        except Exception:
            pass
        # If process has exited, read remaining output
        if self._process.poll() is not None:
            try:
                return self._process.stdout.read().decode("utf-8", errors="replace")
            except Exception:
                pass
        return ""

    def wait_ready(self, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
        """Block until the server responds to a gRPC health check.

        Returns True if the server became ready, False on timeout.
        """
        if self._process is None:
            return False

        target = f"localhost:{self._port}"
        deadline = time.monotonic() + timeout
        logger.info("Waiting for server at %s (timeout=%.0fs)...", target, timeout)

        while time.monotonic() < deadline:
            if not self.is_running():
                output = self.get_output()
                logger.warning("Server process exited before becoming ready. Output:\n%s", output)
                self._last_error = output
                return False
            try:
                channel = grpc.insecure_channel(target)
                grpc.channel_ready_future(channel).result(timeout=poll_interval)
                channel.close()
                logger.info("Server is ready at %s", target)
                return True
            except grpc.FutureTimeoutError:
                pass
            except Exception:
                time.sleep(poll_interval)

        logger.warning("Server did not become ready within %.0fs", timeout)
        self._last_error = f"Timeout after {timeout}s waiting for server at {target}"
        return False

    def stop(self, grace: float = 5.0) -> None:
        """Gracefully terminate the server subprocess."""
        if self._process is None or self._process.poll() is not None:
            self._process = None
            return

        pid = self._process.pid
        logger.info("Stopping server (pid=%s)...", pid)

        self._process.terminate()
        try:
            self._process.wait(timeout=grace)
            logger.info("Server stopped gracefully (pid=%s)", pid)
        except subprocess.TimeoutExpired:
            logger.warning("Server did not stop in %.0fs, killing (pid=%s)", grace, pid)
            self._process.kill()
            self._process.wait(timeout=5)

        self._process = None
