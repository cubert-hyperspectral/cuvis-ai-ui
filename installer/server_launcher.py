"""Cuvis.AI Server tray-icon launcher.

Invoked via ``server-launcher.cmd`` (which prepends bundled ffmpeg/graphviz
to PATH and runs the per-user server-venv's ``pythonw.exe``). Runs the
gRPC server on a daemon thread, redirects stdout/stderr to ``server.log``
in the user data dir, and presents a system tray icon with status / log /
quit actions.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def _user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Cubert GmbH" / "Cuvis.AI UI"
    return Path.home() / ".config" / "cuvis-ai-ui"


# --- 1. Redirect stdout/stderr to a rotating-ish log file ------------------
def _open_log() -> tuple[Path, "object"]:
    user_data = _user_data_dir()
    user_data.mkdir(parents=True, exist_ok=True)
    log_path = user_data / "server.log"
    fh = open(log_path, "a", encoding="utf-8", buffering=1)
    fh.write(f"\n--- server start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    return log_path, fh


_LOG_PATH, _LOG_FH = _open_log()
sys.stdout = _LOG_FH
sys.stderr = _LOG_FH


# --- 2. Run the gRPC server on a daemon thread -----------------------------
_server_started = threading.Event()
_server_failed: list[BaseException] = []


def _run_server() -> None:
    try:
        from cuvis_ai_core.grpc.production_server import serve

        _server_started.set()
        serve()
    except BaseException as exc:  # noqa: BLE001
        _server_failed.append(exc)
        _server_started.set()
        raise


# --- 3. Tray icon ----------------------------------------------------------
def _make_icon():
    import pystray
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), color=(30, 50, 80))
    draw = ImageDraw.Draw(img)
    draw.ellipse((14, 14, 50, 50), fill=(0, 200, 80))

    port = os.environ.get("GRPC_PORT", "50051")
    icon = pystray.Icon(
        name="cuvis-ai-server",
        icon=img,
        title=f"Cuvis.AI Server — listening on :{port}",
    )

    def on_open_log(_icon, _item):
        if sys.platform == "win32":
            os.startfile(str(_LOG_PATH))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(_LOG_PATH)])

    def on_open_data_dir(_icon, _item):
        if sys.platform == "win32":
            os.startfile(str(_LOG_PATH.parent))

    def on_quit(_icon, _item):
        _icon.stop()
        os._exit(0)

    icon.menu = pystray.Menu(
        pystray.MenuItem(f"Cuvis.AI Server (port {port})", None, enabled=False),
        pystray.MenuItem("Open log…", on_open_log),
        pystray.MenuItem("Open data folder…", on_open_data_dir),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )
    return icon


def main() -> None:
    threading.Thread(target=_run_server, name="grpc-serve", daemon=True).start()

    # Give the server a moment to bind so a port-collision crash surfaces
    # before we paint the tray icon.
    _server_started.wait(timeout=2.0)
    if _server_failed:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Cuvis.AI Server failed to start:\n\n{_server_failed[0]}\n\n"
                f"See {_LOG_PATH} for details.",
                "Cuvis.AI Server",
                0x10,  # MB_ICONERROR
            )
        except Exception:
            pass
        sys.exit(1)

    _make_icon().run()


if __name__ == "__main__":
    main()
