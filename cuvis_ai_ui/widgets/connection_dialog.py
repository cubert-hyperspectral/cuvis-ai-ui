"""Connection settings dialog for cuvis-ai visualizer."""

from __future__ import annotations

from typing import Any

import grpc
from loguru import logger
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from cuvis_ai_ui.settings.connection import (
    get_default_connection_settings,
    load_connection_settings,
    save_connection_settings,
)


class ConnectionDialog(QDialog):
    """Dialog for configuring the gRPC server connection.

    Lets the user choose between a local auto-started server or a remote one
    and persists the choice to ``connection.json``.
    """

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Server Connection")
        self.setMinimumWidth(420)

        self._settings = load_connection_settings()
        self._setup_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Mode selection -------------------------------------------
        mode_group = QGroupBox("Server Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._local_radio = QRadioButton("Local server (auto-start)")
        self._remote_radio = QRadioButton("Remote server")

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._local_radio)
        self._mode_group.addButton(self._remote_radio)

        mode_layout.addWidget(self._local_radio)
        mode_layout.addWidget(self._remote_radio)
        layout.addWidget(mode_group)

        # --- Local settings -------------------------------------------
        self._local_group = QGroupBox("Local Server")
        local_layout = QFormLayout(self._local_group)

        self._local_port = QSpinBox()
        self._local_port.setRange(1024, 65535)
        local_layout.addRow("Port:", self._local_port)

        layout.addWidget(self._local_group)

        # --- Remote settings ------------------------------------------
        self._remote_group = QGroupBox("Remote Server")
        remote_layout = QFormLayout(self._remote_group)

        self._remote_host = QLineEdit()
        self._remote_host.setPlaceholderText("e.g. 192.168.1.100")
        remote_layout.addRow("Host:", self._remote_host)

        self._remote_port = QSpinBox()
        self._remote_port.setRange(1, 65535)
        remote_layout.addRow("Port:", self._remote_port)

        layout.addWidget(self._remote_group)

        # --- Test connection ------------------------------------------
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._test_connection)
        self._test_status = QLabel("")
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status, 1)
        layout.addLayout(test_row)

        # --- Dialog buttons -------------------------------------------
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults,
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        restore_btn = btn_box.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        if restore_btn:
            restore_btn.clicked.connect(self._restore_defaults)
        layout.addWidget(btn_box)

        # --- Toggle visibility ----------------------------------------
        self._local_radio.toggled.connect(self._on_mode_changed)
        self._remote_radio.toggled.connect(self._on_mode_changed)

    # ------------------------------------------------------------------
    # Value handling
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        s = self._settings
        if s["mode"] == "remote":
            self._remote_radio.setChecked(True)
        else:
            self._local_radio.setChecked(True)
        self._local_port.setValue(s["port"])
        self._remote_host.setText(s.get("host", "localhost"))
        self._remote_port.setValue(s["port"])
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        is_local = self._local_radio.isChecked()
        self._local_group.setEnabled(is_local)
        self._remote_group.setEnabled(not is_local)
        self._test_status.setText("")

    def _restore_defaults(self) -> None:
        self._settings = get_default_connection_settings()
        self._load_values()

    def get_settings(self) -> dict[str, Any]:
        """Return the current dialog values as a settings dict."""
        if self._local_radio.isChecked():
            return {
                "mode": "local",
                "host": "localhost",
                "port": self._local_port.value(),
                "auto_start": True,
            }
        return {
            "mode": "remote",
            "host": self._remote_host.text().strip() or "localhost",
            "port": self._remote_port.value(),
            "auto_start": False,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _test_connection(self) -> None:
        settings = self.get_settings()
        target = f"{settings['host']}:{settings['port']}"
        self._test_status.setText("Connecting...")
        self._test_status.setStyleSheet("")
        self._test_btn.setEnabled(False)

        # Force a repaint so the label is visible
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        try:
            channel = grpc.insecure_channel(target)
            grpc.channel_ready_future(channel).result(timeout=5)
            channel.close()
            self._test_status.setText("Connected")
            self._test_status.setStyleSheet("color: green;")
        except Exception as exc:
            logger.debug(f"Test connection to {target} failed: {exc}")
            self._test_status.setText("Failed")
            self._test_status.setStyleSheet("color: red;")
        finally:
            self._test_btn.setEnabled(True)

    def _on_accept(self) -> None:
        settings = self.get_settings()
        save_connection_settings(settings)
        self.accept()
