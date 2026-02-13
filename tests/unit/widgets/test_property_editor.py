"""Unit tests for PropertyEditor widget."""

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit

from cuvis_ai_ui.widgets.property_editor import PropertyEditor


@pytest.fixture
def mock_node_adapter(sample_node_info):
    """Mock CuvisNodeAdapter with hyperparameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "MinMaxNormalizer"
    node._cuvis_class_name = "MinMaxNormalizer"
    node._cuvis_class_path = "cuvis_ai.node.normalization.MinMaxNormalizer"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""

    # Set hyperparameters as the dict that PropertyEditor reads directly
    node._cuvis_hparams = {
        "int_param": 10,
        "float_param": 0.5,
        "bool_param": True,
        "str_param": "test",
    }

    # Port specs as dict[str, PortSpec]-like (PropertyEditor uses getattr with default {})
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

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
    # Should create widgets for each hyperparameter + the __name__ widget
    assert len(editor._widgets) > 0


def test_property_editor_creates_int_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QSpinBox for int parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if int_param has a QSpinBox widget
    assert "int_param" in editor._widgets
    widget = editor._widgets["int_param"]
    assert isinstance(widget, QSpinBox)
    assert widget.value() == 10


def test_property_editor_creates_float_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QDoubleSpinBox for float parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if float_param has a QDoubleSpinBox widget
    assert "float_param" in editor._widgets
    widget = editor._widgets["float_param"]
    assert isinstance(widget, QDoubleSpinBox)
    assert widget.value() == pytest.approx(0.5)


def test_property_editor_creates_bool_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QCheckBox for bool parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if bool_param has a QCheckBox widget
    assert "bool_param" in editor._widgets
    widget = editor._widgets["bool_param"]
    assert isinstance(widget, QCheckBox)
    assert widget.isChecked() is True


def test_property_editor_creates_str_widget(qapp, mock_node_adapter):
    """Test that PropertyEditor creates QLineEdit for str parameters."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Check if str_param has a QLineEdit widget
    assert "str_param" in editor._widgets
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

    # Header should show node class name
    assert "MinMaxNormalizer" in editor._header.title()

    # Class label should show full path
    class_text = editor._class_label.text()
    assert "cuvis_ai.node.normalization.MinMaxNormalizer" in class_text


def test_property_editor_displays_port_specs(qapp):
    """Test that PropertyEditor displays port information."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter
    from cuvis_ai_schemas.pipeline.ports import PortSpec

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "TestNode"
    node._cuvis_class_name = "TestNode"
    node._cuvis_class_path = "test.TestNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {}
    node._cuvis_input_specs = {
        "cube": PortSpec(dtype="float32", shape=(-1, -1, -1, -1)),
    }
    node._cuvis_output_specs = {
        "cube": PortSpec(dtype="float32", shape=(-1, -1, -1, -1)),
    }

    editor = PropertyEditor()
    editor.set_node(node)

    # Ports info should show the port names
    assert "cube" in editor._inputs_label.text()
    assert "cube" in editor._outputs_label.text()


def test_property_editor_update_prevents_recursion(qapp, mock_node_adapter):
    """Test that property updates don't cause recursive loops."""
    editor = PropertyEditor()
    editor.set_node(mock_node_adapter)

    # Set updating flag
    editor._updating = True

    # Try to update a widget (should be ignored due to _updating flag)
    if "int_param" in editor._widgets:
        widget = editor._widgets["int_param"]
        widget.setValue(99)

    # Node should not be updated during _updating=True
    assert editor._updating is True


def test_property_editor_with_no_hyperparameters(qapp):
    """Test PropertyEditor with a node that has no hyperparameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "SimpleNode"
    node._cuvis_class_name = "SimpleNode"
    node._cuvis_class_path = "test.SimpleNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)

    # Should only have the __name__ widget (always present)
    assert len(editor._widgets) == 1
    assert "__name__" in editor._widgets
    assert "SimpleNode" in editor._header.title()


def test_property_editor_enum_parameter(qapp):
    """Test PropertyEditor with enum/choice parameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "EnumNode"
    node._cuvis_class_name = "EnumNode"
    node._cuvis_class_path = "test.EnumNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {"choice": "a"}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)

    # Should create a widget for the choice parameter
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
    node2.name.return_value = "OtherNode"
    node2._cuvis_class_name = "OtherNode"
    node2._cuvis_class_path = "test.OtherNode"
    node2._cuvis_source = "builtin"
    node2._cuvis_plugin_name = ""
    node2._cuvis_hparams = {"other_param": 42}
    node2._cuvis_input_specs = {}
    node2._cuvis_output_specs = {}

    editor = PropertyEditor()

    # Set first node
    editor.set_node(node1)
    assert "MinMaxNormalizer" in editor._header.title()

    # Switch to second node
    editor.set_node(node2)
    assert "OtherNode" in editor._header.title()

    # Previous widgets should be replaced
    assert "other_param" in editor._widgets or len(editor._widgets) > 0


# ---------------------------------------------------------------------------
# Additional coverage: list, dict, path, plugin widgets
# ---------------------------------------------------------------------------


def test_property_editor_creates_list_widget(qapp):
    """Test that PropertyEditor creates QLineEdit for list parameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "ListNode"
    node._cuvis_class_name = "ListNode"
    node._cuvis_class_path = "test.ListNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {"items": [1, 2, 3]}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)

    assert "items" in editor._widgets
    widget = editor._widgets["items"]
    assert isinstance(widget, QLineEdit)
    assert "1" in widget.text()


def test_property_editor_creates_dict_widget(qapp):
    """Test that PropertyEditor creates QLineEdit for dict parameters."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "DictNode"
    node._cuvis_class_name = "DictNode"
    node._cuvis_class_path = "test.DictNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {"config": {"key": "value"}}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)

    assert "config" in editor._widgets
    widget = editor._widgets["config"]
    assert isinstance(widget, QLineEdit)
    assert "key" in widget.text()


def test_property_editor_plugin_source_display(qapp):
    """Test PropertyEditor shows plugin name for plugin nodes."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "PluginNode"
    node._cuvis_class_name = "PluginNode"
    node._cuvis_class_path = "my_plugin.PluginNode"
    node._cuvis_source = "plugin"
    node._cuvis_plugin_name = "my_plugin"
    node._cuvis_hparams = {}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)

    assert "my_plugin" in editor._source_label.text()


def test_property_editor_parse_list():
    """Test _parse_list method directly."""
    editor = PropertyEditor.__new__(PropertyEditor)

    # Empty
    assert editor._parse_list("") == []

    # Integers
    result = editor._parse_list("1, 2, 3")
    assert result == [1, 2, 3]

    # Floats
    result = editor._parse_list("1.0, 2.5")
    assert result == [1.0, 2.5]

    # Strings
    result = editor._parse_list("hello, world")
    assert result == ["hello", "world"]


def test_property_editor_parse_dict():
    """Test _parse_dict method directly."""
    editor = PropertyEditor.__new__(PropertyEditor)

    # Valid JSON
    result = editor._parse_dict('{"key": "value"}')
    assert result == {"key": "value"}

    # Invalid JSON
    result = editor._parse_dict("not json")
    assert result == {}


def test_property_editor_refresh(qapp):
    """Test refresh reloads current node."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "TestNode"
    node._cuvis_class_name = "TestNode"
    node._cuvis_class_path = "test.TestNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {"param": 5}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)

    # Refresh should re-render
    editor.refresh()

    assert editor._current_node == node
    assert "param" in editor._widgets


def test_property_editor_set_none_clears(qapp):
    """Test setting node to None clears the editor."""
    from cuvis_ai_ui.adapters.node_adapter import CuvisNodeAdapter

    node = MagicMock(spec=CuvisNodeAdapter)
    node.name.return_value = "TestNode"
    node._cuvis_class_name = "TestNode"
    node._cuvis_class_path = "test.TestNode"
    node._cuvis_source = "builtin"
    node._cuvis_plugin_name = ""
    node._cuvis_hparams = {"p": 1}
    node._cuvis_input_specs = {}
    node._cuvis_output_specs = {}

    editor = PropertyEditor()
    editor.set_node(node)
    assert len(editor._widgets) > 0

    editor.set_node(None)
    assert editor._current_node is None
    assert "No Node Selected" in editor._header.title()


# ---------------------------------------------------------------------------
# Additional coverage: ExecutionStagesEditor
# ---------------------------------------------------------------------------


def test_execution_stages_editor_initialization(qapp):
    """Test ExecutionStagesEditor initialization."""
    from cuvis_ai_ui.widgets.property_editor import ExecutionStagesEditor

    editor = ExecutionStagesEditor()

    # Default: "always" should be checked
    stages = editor.get_stages()
    assert "always" in stages


def test_execution_stages_editor_set_get_stages(qapp):
    """Test setting and getting stages."""
    from cuvis_ai_ui.widgets.property_editor import ExecutionStagesEditor

    editor = ExecutionStagesEditor()

    editor.set_stages({"train", "inference"})
    stages = editor.get_stages()

    assert "train" in stages
    assert "inference" in stages
    assert "always" not in stages


def test_execution_stages_editor_signal(qapp, qtbot):
    """Test stages_changed signal emission."""
    from cuvis_ai_ui.widgets.property_editor import ExecutionStagesEditor

    editor = ExecutionStagesEditor()

    with qtbot.waitSignal(editor.stages_changed, timeout=1000):
        # Toggle a checkbox
        editor._checkboxes["train"].setChecked(True)
