"""Pipeline information dialog for viewing and editing metadata.

This dialog allows users to view and edit pipeline metadata including:
- Name
- Description
- Tags
- Author
- Created timestamp (auto-generated)
- Additional custom fields (read-only)
"""

from datetime import datetime
from typing import Any

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class PipelineInfoDialog(QDialog):
    """Dialog for viewing and editing pipeline metadata.

    Provides form fields for standard metadata:
    - Name (required)
    - Description
    - Tags (comma-separated)
    - Author
    - Created timestamp (auto-generated, read-only)

    Additional custom metadata fields are displayed read-only.
    """

    def __init__(
        self,
        metadata: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the pipeline info dialog.

        Args:
            metadata: Current pipeline metadata dict
            parent: Parent widget
        """
        super().__init__(parent)

        self._metadata = metadata or {}
        self._setup_ui()
        self._load_metadata()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Pipeline Information")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Main form layout
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Name field (required)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter pipeline name (required)")
        form_layout.addRow("Name:", self._name_edit)

        # Description field (multi-line)
        self._description_edit = QTextEdit()
        self._description_edit.setPlaceholderText("Enter pipeline description")
        self._description_edit.setMaximumHeight(100)
        form_layout.addRow("Description:", self._description_edit)

        # Tags field (comma-separated)
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("tag1, tag2, tag3")
        form_layout.addRow("Tags:", self._tags_edit)

        # Author field
        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("Enter author name")
        form_layout.addRow("Author:", self._author_edit)

        # Created field (read-only, auto-generated)
        self._created_label = QLabel()
        self._created_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form_layout.addRow("Created:", self._created_label)

        layout.addLayout(form_layout)

        # Additional fields section (read-only)
        self._extra_fields_group = QGroupBox("Additional Fields")
        self._extra_fields_layout = QFormLayout()
        self._extra_fields_group.setLayout(self._extra_fields_layout)
        layout.addWidget(self._extra_fields_group)

        # Initially hide if no extra fields
        self._extra_fields_group.setVisible(False)

        # Spacer
        layout.addStretch()

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_metadata(self) -> None:
        """Load metadata into form fields."""
        # Load standard fields from metadata dict with defaults
        name = self._metadata.get("name", "")
        description = self._metadata.get("description", "")
        tags = self._metadata.get("tags", [])
        author = self._metadata.get("author", "")
        created = self._metadata.get("created", "")

        self._name_edit.setText(name)
        self._description_edit.setPlainText(description)

        # Handle tags as list or string
        if isinstance(tags, list):
            self._tags_edit.setText(", ".join(tags))
        else:
            self._tags_edit.setText(str(tags))

        self._author_edit.setText(author)

        # Created timestamp
        if created:
            self._created_label.setText(created)
        else:
            self._created_label.setText("(Will be set on save)")
            self._created_label.setStyleSheet("color: gray; font-style: italic;")

        # Load extra fields (non-standard metadata)
        standard_fields = {
            "name",
            "description",
            "tags",
            "author",
            "created",
        }
        extra_fields = {
            k: v for k, v in self._metadata.items() if k not in standard_fields
        }

        if extra_fields:
            self._extra_fields_group.setVisible(True)
            for key, value in extra_fields.items():
                label = QLabel(str(value))
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                label.setWordWrap(True)
                self._extra_fields_layout.addRow(f"{key}:", label)

    def _on_accept(self) -> None:
        """Validate and accept the dialog."""
        # Validate name (required)
        name = self._name_edit.text().strip()
        if not name:
            self._name_edit.setFocus()
            self._name_edit.setStyleSheet("border: 1px solid red;")
            logger.warning("Pipeline name is required")
            return

        # Reset style
        self._name_edit.setStyleSheet("")

        # Accept dialog
        self.accept()

    def get_metadata(self) -> dict[str, Any]:
        """Get the updated metadata from form fields.

        Returns:
            Updated metadata dictionary
        """
        # Parse tags (comma-separated)
        tags_text = self._tags_edit.text().strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

        # Auto-generate created timestamp if not present
        created = self._metadata.get("created", "")
        if not created:
            created = datetime.now().isoformat()

        # Build updated metadata
        updated = {
            "name": self._name_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "tags": tags,
            "author": self._author_edit.text().strip(),
            "created": created,
        }

        # Preserve extra fields
        standard_fields = {"name", "description", "tags", "author", "created"}
        for key, value in self._metadata.items():
            if key not in standard_fields:
                updated[key] = value

        # Remove empty values
        return {k: v for k, v in updated.items() if v}
