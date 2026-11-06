"""Dock widget listing the pipelines of one folder."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ..workspace import list_pipelines

_PATH_ROLE = Qt.ItemDataRole.UserRole


class PipelineBrowser(QWidget):
    """List of the pipeline YAML files in a folder.

    Selecting an entry, with the mouse or the arrow keys, emits
    ``pipeline_selected`` with the file path; the main window opens it.

    Signals:
        pipeline_selected: A pipeline was chosen (path: str)
    """

    pipeline_selected = Signal(str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None
        self._pipelines: list[Path] = []

        self.list_widget = QListWidget(self)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.empty_label = QLabel(self)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.list_widget)
        self.set_folder(None)

    @property
    def folder(self) -> Path | None:
        """The folder shown, or None."""
        return self._folder

    @property
    def pipelines(self) -> list[Path]:
        """The listed pipeline files, in display order."""
        return list(self._pipelines)

    def set_folder(self, folder: str | Path | None) -> None:
        """Show the pipelines of ``folder`` (None clears the list)."""
        self._folder = Path(folder) if folder is not None else None
        self._pipelines = list_pipelines(self._folder) if self._folder is not None else []

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for path in self._pipelines:
            item = QListWidgetItem(path.stem)
            item.setToolTip(str(path))
            item.setData(_PATH_ROLE, str(path))
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(-1)
        self.list_widget.blockSignals(False)

        if self._folder is None:
            self.empty_label.setText("Open a folder of pipelines with File > Open Folder.")
        elif not self._pipelines:
            self.empty_label.setText(f"No pipelines in {self._folder}")
        else:
            self.empty_label.setText("")
        self.empty_label.setHidden(bool(self._pipelines))
        self.list_widget.setHidden(not self._pipelines)

    def select(self, path: str | Path | None) -> None:
        """Mark ``path`` as the open pipeline without emitting ``pipeline_selected``."""
        row = -1
        if path is not None:
            try:
                row = self._pipelines.index(Path(path))
            except ValueError:
                row = -1
        self.list_widget.blockSignals(True)
        self.list_widget.setCurrentRow(row)
        self.list_widget.blockSignals(False)

    def _on_current_changed(self, current: QListWidgetItem | None, _previous: Any) -> None:
        if current is not None:
            self.pipeline_selected.emit(current.data(_PATH_ROLE))
