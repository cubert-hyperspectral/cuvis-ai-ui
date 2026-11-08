"""Run a blocking call off the UI thread behind a progress dialog with Cancel.

Starting the local server, connecting and registering plugins are blocking
gRPC calls. Run on the UI thread they freeze every window for as long as they
take. :func:`run_blocking` runs such a call on a worker thread and shows an
application-modal progress dialog meanwhile: windows repaint, no other action
can start, and Cancel tells the worker to stop at its next checkpoint.

The worker never touches a Qt object. A timer on the UI thread checks whether
it finished, and every Qt update happens on the UI thread after the runner
returns.
"""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from loguru import logger
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QProgressDialog, QWidget

from ..grpc.client import OperationCancelled
from ..server import SERVER_READY_TIMEOUT

if TYPE_CHECKING:
    from ..server import ServerManager

T = TypeVar("T")

# How often the UI thread checks whether the worker finished.
_POLL_MS = 50

# Status bar note after the user stops waiting for a starting server.
SERVER_WAIT_CANCELLED = (
    "Stopped waiting for the local server. It keeps starting; "
    "use Tools > Connect to Server once it is up."
)


class TaskStatus(enum.Enum):
    """How a blocking task ended."""

    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult(Generic[T]):
    """Outcome of :func:`run_blocking`: the work's value or the error text."""

    status: TaskStatus
    value: T | None = None
    error: str = ""


def run_blocking(
    parent: QWidget | None,
    title: str,
    text: str,
    work: Callable[[threading.Event], T],
) -> TaskResult[T]:
    """Run ``work(stop)`` on a worker thread and wait behind a modal dialog.

    ``work`` receives a :class:`threading.Event` that Cancel, Esc or closing
    the dialog sets; it should check it between its blocking calls and raise
    :class:`~cuvis_ai_ui.grpc.client.OperationCancelled` when set. After a
    Cancel the dialog says "Cancelling..." until the worker returns, so the
    runner never returns while the worker still uses a client or a manager.

    A ``work`` that returns a value is DONE even when Cancel came during its
    last call: the work happened, and dropping it (a connect that went
    through, say) would leave server state behind. Any other exception is
    FAILED with its message.
    """
    stop = threading.Event()
    outcome: list[TaskResult[T]] = []

    def run() -> None:
        try:
            result: TaskResult[T] = TaskResult(TaskStatus.DONE, value=work(stop))
        except OperationCancelled:
            result = TaskResult(TaskStatus.CANCELLED)
        except BaseException as exc:  # noqa: BLE001 - every failure must end the wait
            logger.opt(exception=exc).warning(f"{title} failed: {exc}")
            result = TaskResult(TaskStatus.FAILED, error=str(exc) or type(exc).__name__)
        outcome.append(result)

    dialog = QProgressDialog(text, "Cancel", 0, 0, parent)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    finished = False

    def on_cancel() -> None:
        # QProgressDialog hides itself on Cancel; show it again as
        # "Cancelling..." so the windows stay blocked until the worker returns.
        if finished or stop.is_set():
            return
        stop.set()
        dialog.setLabelText("Cancelling...")
        dialog.setCancelButton(None)
        dialog.show()

    dialog.canceled.connect(on_cancel)
    dialog.rejected.connect(on_cancel)

    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(_POLL_MS)
    timer.timeout.connect(lambda: loop.quit() if outcome else None)

    worker = threading.Thread(target=run, name=f"blocking-task: {title}", daemon=True)
    dialog.show()
    worker.start()
    timer.start()
    if not outcome:
        loop.exec()
    timer.stop()
    worker.join()

    finished = True
    dialog.hide()
    dialog.deleteLater()
    return outcome[0]


def wait_for_server(manager: ServerManager, parent: QWidget | None) -> TaskResult[bool]:
    """Wait for a freshly started local server; DONE with False means not ready."""
    text = (
        f"Starting the local cuvis-ai-core server on port {manager.port}...\n\n"
        f"Server log: {manager.log_path}"
    )
    return run_blocking(
        parent,
        "Starting server",
        text,
        lambda stop: manager.wait_ready(timeout=SERVER_READY_TIMEOUT, stop=stop),
    )
