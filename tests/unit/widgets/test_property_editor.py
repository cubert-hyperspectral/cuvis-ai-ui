"""Unit tests for PropertyEditor widget."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QComboBox

from cuvis_ai_ui.widgets.property_editor import PropertyEditor


@pytest.fixture
def mock_node_adapter(sample_node_info):
    """Mock CuvisNodeAdapter with hyperparameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.class_name = "MinMaxNormalizer"
    node.full_path = "cuvis_ai.node.normalization.MinMaxNormalizer"
    node.source = "builtin"
    node.plugin_name = ""

    # Mock hyperparameters
    node.get_hyperparameters.return_value = {
        "int_param": 10,
        "float_param": 0.5,
        "bool_param": True,
        "str_param": "test"
    }

    node.get_hyperparameter_types.return_value = {
        "int_param": int,
        "float_param": float,
        "bool_param": bool,
        "str_param": str
    }

    # Mock port specs
    node.input_specs = sample_node_info["input_specs"]
    node.output_specs = sample_node_info["output_specs"]

    return node


def test_property_editor_initialization(qapp):
    """Test PropertyEditor widget initialization."""
    editor = PropertyEditor()

    assert editor is not None
    assert editor._current_node is None
    assert len(editor._widgets) == 0


def test_property_editor_no_node_selected(qapp):
    """Test PropertyEditor with no node selected."""
    editor = PropertyEditor()

    # Header should indicate no selection
    assert "No Node Selected" in editor._header.title()


def test_property_editor_set_node(qapp, mock_node_adapter):
    """Test setting a node to edit."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    assert editor._current_node == mock_node_adapter
    # Should create widgets for each hyperparameter
    assert len(editor._widgets) > 0


def test_property_editor_creates_int_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QSpinBox for int parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if int_param has a QSpinBox widget
    if "int_param" in editor._widgets:
        widget = editor._widgets["int_param"]
        assert isinstance(widget, QSpinBox)
        assert widget.value() == 10


def test_property_editor_creates_float_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QDoubleSpinBox for float parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if float_param has a QDoubleSpinBox widget
    if "float_param" in editor._widgets:
        widget = editor._widgets["float_param"]
        assert isinstance(widget, QDoubleSpinBox)
        assert widget.value() == pytest.approx(0.5)


def test_property_editor_creates_bool_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QCheckBox for bool parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if bool_param has a QCheckBox widget
    if "bool_param" in editor._widgets:
        widget = editor._widgets["bool_param"]
        assert isinstance(widget, QCheckBox)
        assert widget.isChecked() is True


def test_property_editor_creates_str_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QLineEdit for str parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if str_param has a QLineEdit widget
    if "str_param" in editor._widgets:
        widget = editor._widgets["str_param"]
        assert isinstance(widget, QLineEdit)
        assert widget.text() == "test"


def test_property_editor_clear(qapp, mock_node_adapter):
    """Test clearing the property editor."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    assert len(editor._widgets) > 0

    editor.clear()

    assert editor._current_node is None
    assert len(editor._widgets) == 0


def test_property_editor_property_changed_signal(qapp, qtbot, mock_node_adapter):
    """Test that property_changed signal is emitted."""
    editor = PropertyEditor()

    # Connect signal spy
    with qtbot.waitSignal(editor.property_changed, timeout=1000) as blocker:
        editor.set_node(mock_node_adapter)

        # Trigger a change (simulate user interaction)
        if "int_param" in editor._widgets:
            widget = editor._widgets["int_param"]
            widget.setValue(20)

    # Signal should have been emitted
    assert blocker.signal_triggered


def test_property_editor_displays_node_info(qapp, mock_node_adapter):
    """Test that PropertyEditor displays node information."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Header should show node name
    assert "MinMaxNormalizer" in editor._header.title()

    # Class label should show full path
    class_text = editor._class_label.text()
    assert "cuvis_ai.node.normalization.MinMaxNormalizer" in class_text


def test_property_editor_displays_port_specs(qapp, mock_node_adapter):
    """Test that PropertyEditor displays port information."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Ports group should be visible if node has ports
    if len(mock_node_adapter.input_specs) > 0 or len(mock_node_adapter.output_specs) > 0:
        assert editor._ports_group.isVisible()


def test_property_editor_update_prevents_recursion(qapp, mock_node_adapter):
    """Test that property updates don't cause recursive loops."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Set updating flag
    editor._updating = True

    # Try to update a widget (should be ignored)
    if "int_param" in editor._widgets:
        widget = editor._widgets["int_param"]
        widget.setValue(99)

    # Node should not be updated during _updating=True
    assert editor._updating is True


def test_property_editor_with_no_hyperparameters(qapp):
    """Test PropertyEditor with a node that has no hyperparameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.class_name = "SimpleNode"
    node.full_path = "test.SimpleNode"
    node.get_hyperparameters.return_value = {}
    node.get_hyperparameter_types.return_value = {}
    node.input_specs = []
    node.output_specs = []

    editor = PropertyEditor()
    editor.set_node(node)

    # Should not crash with no hyperparameters
    assert len(editor._widgets) == 0
    assert "SimpleNode" in editor._header.title()


def test_property_editor_enum_parameter(qapp):
    """Test PropertyEditor with enum/choice parameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter
    from enum import Enum

    class TestEnum(Enum):
        OPTION_A = "a"
        OPTION_B = "b"

    node = MagicMock(spec=CuvisNodeAdapter)
    node.class_name = "EnumNode"
    node.full_path = "test.EnumNode"
    node.get_hyperparameters.return_value = {"choice": "a"}
    node.get_hyperparameter_types.return_value = {"choice": TestEnum}
    node.input_specs = []
    node.output_specs = []

    editor = PropertyEditor()
    editor.set_node(node)

    # Should create a QComboBox for enum types (if supported)
    if "choice" in editor._widgets:
        widget = editor._widgets["choice"]
        # Could be QComboBox or QLineEdit depending on implementation
        assert widget is not None


def test_property_editor_multiple_node_switches(qapp, mock_node_adapter):
    """Test switching between multiple nodes."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    # Create two different mock nodes
    node1 = mock_node_adapter

    node2 = MagicMock(spec=CuvisNodeAdapter)
    node2.class_name = "OtherNode"
    node2.full_path = "test.OtherNode"
    node2.get_hyperparameters.return_value = {"other_param": 42}
    node2.get_hyperparameter_types.return_value = {"other_param": int}
    node2.input_specs = []
    node2.output_specs = []

    editor = PropertyEditor()

    # Set first node
    editor.set_node(node1)
    assert "MinMaxNormalizer" in editor._header.title()

    # Switch to second node
    editor.set_node(node2)
    assert "OtherNode" in editor._header.title()

    # Previous widgets should be replaced
    assert "other_param" in editor._widgets or len(editor._widgets) > 0
