"""Property editor widget for editing node hyperparameters.

This module provides a dynamic form generator that creates appropriate
Qt widgets for different parameter types:
- int -> QSpinBox
- float -> QDoubleSpinBox
- bool -> QCheckBox
- str -> QLineEdit
- enum -> QComboBox
- Path -> QLineEdit + file picker button
"""

from pathlib import Path
from typing import Any, Callable

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..adapters import CuvisNodeAdapter, PortSpec


class PropertyEditor(QWidget):
    """Dynamic property editor for cuvis-ai nodes.

    Generates appropriate form widgets based on parameter types
    and updates node hyperparameters in real-time.

    Signals:
        property_changed: Emitted when a property is changed (key: str, value: Any)
    """

    property_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the property editor.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._current_node: CuvisNodeAdapter | None = None
        self._widgets: dict[str, QWidget] = {}
        self._updating = False  # Prevent recursive updates

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Node info header
        self._header = QGroupBox("No Node Selected")
        header_layout = QVBoxLayout(self._header)

        self._class_label = QLabel()
        self._class_label.setWordWrap(True)
        header_layout.addWidget(self._class_label)

        self._source_label = QLabel()
        header_layout.addWidget(self._source_label)

        layout.addWidget(self._header)

        # Scrollable properties area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._properties_widget = QWidget()
        self._properties_layout = QFormLayout(self._properties_widget)
        self._properties_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        scroll.setWidget(self._properties_widget)
        layout.addWidget(scroll, 1)

        # Ports info
        self._ports_group = QGroupBox("Ports")
        ports_layout = QVBoxLayout(self._ports_group)

        self._inputs_label = QLabel("Inputs: None")
        self._inputs_label.setWordWrap(True)
        ports_layout.addWidget(self._inputs_label)

        self._outputs_label = QLabel("Outputs: None")
        self._outputs_label.setWordWrap(True)
        ports_layout.addWidget(self._outputs_label)

        layout.addWidget(self._ports_group)

    def set_node(self, node: CuvisNodeAdapter | None) -> None:
        """Set the node to edit.

        Args:
            node: The node to edit, or None to clear
        """
        self._current_node = node
        self._widgets.clear()

        # Clear existing widgets
        while self._properties_layout.count():
            item = self._properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if node is None:
            self._header.setTitle("No Node Selected")
            self._class_label.clear()
            self._source_label.clear()
            self._inputs_label.setText("Inputs: None")
            self._outputs_label.setText("Outputs: None")
            return

        # Update header
        class_name = getattr(node, "_cuvis_class_name", node.name())
        class_path = getattr(node, "_cuvis_class_path", "")
        source = getattr(node, "_cuvis_source", "")
        plugin = getattr(node, "_cuvis_plugin_name", "")

        self._header.setTitle(class_name)
        self._class_label.setText(f"<i>{class_path}</i>")

        if plugin:
            self._source_label.setText(f"Plugin: {plugin}")
        elif source:
            self._source_label.setText(f"Source: {source}")
        else:
            self._source_label.clear()

        # Add name field (always present)
        name_edit = QLineEdit(node.name())
        name_edit.textChanged.connect(
            lambda text: self._on_name_changed(text)
        )
        self._properties_layout.addRow("Name:", name_edit)
        self._widgets["__name__"] = name_edit

        # Add hyperparameter fields
        hparams = getattr(node, "_cuvis_hparams", {})
        for key, value in hparams.items():
            widget = self._create_widget_for_value(key, value)
            self._properties_layout.addRow(f"{key}:", widget)
            self._widgets[key] = widget

        # Update ports info
        input_specs = getattr(node, "_cuvis_input_specs", {})
        output_specs = getattr(node, "_cuvis_output_specs", {})

        self._update_ports_info(input_specs, output_specs)

    def _create_widget_for_value(self, key: str, value: Any) -> QWidget:
        """Create an appropriate widget for a value type.

        Args:
            key: Parameter key
            value: Parameter value

        Returns:
            Created widget
        """
        if isinstance(value, bool):
            return self._create_bool_widget(key, value)
        elif isinstance(value, int):
            return self._create_int_widget(key, value)
        elif isinstance(value, float):
            return self._create_float_widget(key, value)
        elif isinstance(value, (list, tuple)):
            return self._create_list_widget(key, value)
        elif isinstance(value, dict):
            return self._create_dict_widget(key, value)
        elif isinstance(value, Path):
            return self._create_path_widget(key, value)
        else:
            return self._create_string_widget(key, str(value) if value is not None else "")

    def _create_bool_widget(self, key: str, value: bool) -> QCheckBox:
        """Create a checkbox for boolean values."""
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        checkbox.stateChanged.connect(
            lambda state: self._on_value_changed(key, state == Qt.CheckState.Checked.value)
        )
        return checkbox

    def _create_int_widget(self, key: str, value: int) -> QSpinBox:
        """Create a spinbox for integer values."""
        spinbox = QSpinBox()
        spinbox.setRange(-999999999, 999999999)
        spinbox.setValue(value)
        spinbox.valueChanged.connect(
            lambda val: self._on_value_changed(key, val)
        )
        return spinbox

    def _create_float_widget(self, key: str, value: float) -> QDoubleSpinBox:
        """Create a double spinbox for float values."""
        spinbox = QDoubleSpinBox()
        spinbox.setRange(-1e10, 1e10)
        spinbox.setDecimals(6)
        spinbox.setValue(value)
        spinbox.valueChanged.connect(
            lambda val: self._on_value_changed(key, val)
        )
        return spinbox

    def _create_string_widget(self, key: str, value: str) -> QLineEdit:
        """Create a line edit for string values."""
        edit = QLineEdit(value)
        edit.textChanged.connect(
            lambda text: self._on_value_changed(key, text)
        )
        return edit

    def _create_path_widget(self, key: str, value: Path | str) -> QWidget:
        """Create a line edit with file picker for path values."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        edit = QLineEdit(str(value))
        edit.textChanged.connect(
            lambda text: self._on_value_changed(key, Path(text) if text else None)
        )
        layout.addWidget(edit, 1)

        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(30)
        browse_btn.clicked.connect(
            lambda: self._browse_path(edit)
        )
        layout.addWidget(browse_btn)

        return widget

    def _create_list_widget(self, key: str, value: list | tuple) -> QLineEdit:
        """Create a line edit for list values (as comma-separated)."""
        text = ", ".join(str(v) for v in value)
        edit = QLineEdit(text)
        edit.setPlaceholderText("Comma-separated values")
        edit.textChanged.connect(
            lambda t: self._on_value_changed(key, self._parse_list(t))
        )
        return edit

    def _create_dict_widget(self, key: str, value: dict) -> QLineEdit:
        """Create a line edit for dict values (as JSON-like string)."""
        import json
        text = json.dumps(value)
        edit = QLineEdit(text)
        edit.setPlaceholderText("JSON format: {\"key\": value}")
        edit.textChanged.connect(
            lambda t: self._on_value_changed(key, self._parse_dict(t))
        )
        return edit

    def _parse_list(self, text: str) -> list:
        """Parse comma-separated text into a list."""
        if not text.strip():
            return []
        items = [s.strip() for s in text.split(",")]
        # Try to convert to numbers
        result = []
        for item in items:
            try:
                if "." in item:
                    result.append(float(item))
                else:
                    result.append(int(item))
            except ValueError:
                result.append(item)
        return result

    def _parse_dict(self, text: str) -> dict:
        """Parse JSON-like text into a dict."""
        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def _browse_path(self, edit: QLineEdit) -> None:
        """Open file browser and update path edit.

        Args:
            edit: Line edit to update
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Select File", edit.text()
        )
        if path:
            edit.setText(path)

    def _on_name_changed(self, name: str) -> None:
        """Handle node name change.

        Args:
            name: New node name
        """
        if self._current_node and not self._updating:
            self._current_node.set_name(name)
            self.property_changed.emit("__name__", name)

    def _on_value_changed(self, key: str, value: Any) -> None:
        """Handle property value change.

        Args:
            key: Property key
            value: New value
        """
        if self._current_node and not self._updating:
            self._current_node.update_hparam(key, value)
            self.property_changed.emit(key, value)
            logger.debug(f"Property changed: {key} = {value}")

    def _update_ports_info(
        self,
        inputs: dict[str, PortSpec],
        outputs: dict[str, PortSpec],
    ) -> None:
        """Update the ports information display.

        Args:
            inputs: Input port specifications
            outputs: Output port specifications
        """
        if inputs:
            input_text = "<b>Inputs:</b><br>"
            for name, spec in inputs.items():
                opt = " (opt)" if spec.optional else ""
                input_text += f"  - {name}: {spec.dtype}{opt}<br>"
            self._inputs_label.setText(input_text)
        else:
            self._inputs_label.setText("Inputs: None")

        if outputs:
            output_text = "<b>Outputs:</b><br>"
            for name, spec in outputs.items():
                output_text += f"  - {name}: {spec.dtype}<br>"
            self._outputs_label.setText(output_text)
        else:
            self._outputs_label.setText("Outputs: None")

    def refresh(self) -> None:
        """Refresh the display from the current node."""
        if self._current_node:
            self._updating = True
            try:
                self.set_node(self._current_node)
            finally:
                self._updating = False

    def clear(self) -> None:
        """Clear the editor."""
        self.set_node(None)


class ExecutionStagesEditor(QWidget):
    """Editor for node execution stages.

    Allows selecting which pipeline stages the node executes in:
    - always (default)
    - train
    - val
    - test
    - inference
    """

    stages_changed = Signal(set)

    AVAILABLE_STAGES = ["always", "train", "val", "test", "inference"]

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the editor.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for stage in self.AVAILABLE_STAGES:
            cb = QCheckBox(stage)
            cb.stateChanged.connect(self._on_stage_changed)
            layout.addWidget(cb)
            self._checkboxes[stage] = cb

        # Default to "always"
        self._checkboxes["always"].setChecked(True)

    def _on_stage_changed(self, state: int) -> None:
        """Handle stage checkbox change."""
        stages = self.get_stages()
        self.stages_changed.emit(stages)

    def get_stages(self) -> set[str]:
        """Get the selected stages.

        Returns:
            Set of selected stage names
        """
        return {
            stage for stage, cb in self._checkboxes.items()
            if cb.isChecked()
        }

    def set_stages(self, stages: set[str]) -> None:
        """Set the selected stages.

        Args:
            stages: Set of stage names to select
        """
        for stage, cb in self._checkboxes.items():
            cb.setChecked(stage in stages)
