"""Unit tests for NodePalette widget."""

import pytest
from unittest.mock import Mock, MagicMock

from cuvis_ai_ui.widgets.node_palette import NodePalette, NodePaletteItem


def test_node_palette_item_initialization(sample_node_info):
    """Test NodePaletteItem initialization with node info."""
    mock_parent = MagicMock()

    item = NodePaletteItem(mock_parent, sample_node_info)

    assert item.node_info == sample_node_info
    assert item.text(0) == "MinMaxNormalizer"


def test_node_palette_item_tooltip(sample_node_info):
    """Test that NodePaletteItem generates a tooltip."""
    mock_parent = MagicMock()

    item = NodePaletteItem(mock_parent, sample_node_info)
    tooltip = item.toolTip(0)

    # Tooltip should contain key information
    assert "MinMaxNormalizer" in tooltip
    assert "cube" in tooltip  # port name
    assert "float32" in tooltip  # dtype


def test_node_palette_item_with_empty_specs():
    """Test NodePaletteItem with node that has no port specs."""
    node_info = {
        "class_name": "EmptyNode",
        "full_path": "test.EmptyNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": []
    }

    mock_parent = MagicMock()
    item = NodePaletteItem(mock_parent, node_info)

    assert item.text(0) == "EmptyNode"
    # Should not crash with empty specs
    tooltip = item.toolTip(0)
    assert "EmptyNode" in tooltip


def test_node_palette_initialization(qapp):
    """Test NodePalette widget initialization."""
    mock_graph = MagicMock()

    palette = NodePalette(mock_graph)

    assert palette is not None
    assert palette._graph == mock_graph


def test_node_palette_populate_with_registry(qapp, node_registry):
    """Test populating palette from NodeRegistry."""
    mock_graph = MagicMock()

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(node_registry)

    # Should have created tree items
    assert palette._tree.topLevelItemCount() > 0


def test_node_palette_search_functionality(qapp, node_registry):
    """Test search/filter functionality in palette."""
    mock_graph = MagicMock()

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(node_registry)

    initial_visible = palette._count_visible_items()

    # Search for a specific node
    palette._search_edit.setText("MinMax")
    palette._filter_nodes()

    filtered_visible = palette._count_visible_items()

    # Filtered results should be <= initial results
    assert filtered_visible <= initial_visible


def test_node_palette_clear_search(qapp, node_registry):
    """Test clearing search filter."""
    mock_graph = MagicMock()

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(node_registry)

    initial_visible = palette._count_visible_items()

    # Apply filter
    palette._search_edit.setText("NonExistent")
    palette._filter_nodes()

    # Clear filter
    palette._search_edit.clear()
    palette._filter_nodes()

    final_visible = palette._count_visible_items()

    # Should show all items again
    assert final_visible == initial_visible


def test_node_palette_organizes_by_category(qapp):
    """Test that palette organizes nodes by category/plugin."""
    mock_graph = MagicMock()
    from cuvis_ai_ui.adapters import NodeRegistry

    # Create registry with nodes from different plugins
    registry = NodeRegistry()
    registry.register_nodes([
        {
            "class_name": "Node1",
            "full_path": "plugin1.Node1",
            "source": "plugin",
            "plugin_name": "plugin1",
            "input_specs": [],
            "output_specs": []
        },
        {
            "class_name": "Node2",
            "full_path": "plugin2.Node2",
            "source": "plugin",
            "plugin_name": "plugin2",
            "input_specs": [],
            "output_specs": []
        },
        {
            "class_name": "Builtin",
            "full_path": "cuvis_ai.Builtin",
            "source": "builtin",
            "plugin_name": "",
            "input_specs": [],
            "output_specs": []
        }
    ])

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(registry)

    # Should have multiple top-level categories
    assert palette._tree.topLevelItemCount() > 1


def test_node_palette_refresh(qapp, node_registry):
    """Test refreshing palette with new nodes."""
    mock_graph = MagicMock()

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(node_registry)

    initial_count = palette._tree.topLevelItemCount()

    # Refresh with same registry
    palette.populate_from_registry(node_registry)

    final_count = palette._tree.topLevelItemCount()

    # Count should be consistent after refresh
    assert final_count == initial_count


def test_node_palette_empty_registry(qapp):
    """Test palette with empty NodeRegistry."""
    mock_graph = MagicMock()
    from cuvis_ai_ui.adapters import NodeRegistry

    empty_registry = NodeRegistry()

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(empty_registry)

    # Should not crash with empty registry
    assert palette._tree.topLevelItemCount() >= 0


def test_node_palette_item_selection(qapp, node_registry):
    """Test selecting an item in the palette."""
    mock_graph = MagicMock()

    palette = NodePalette(mock_graph)
    palette.populate_from_registry(node_registry)

    # Get first item
    if palette._tree.topLevelItemCount() > 0:
        category_item = palette._tree.topLevelItem(0)
        if category_item.childCount() > 0:
            node_item = category_item.child(0)

            # Select the item
            palette._tree.setCurrentItem(node_item)

            # Should be selected
            assert palette._tree.currentItem() == node_item


def test_node_palette_port_spec_in_tooltip():
    """Test that PortSpec objects are handled in tooltip."""
    from cuvis_ai_schemas.pipeline.ports import PortSpec

    # Create node info with PortSpec objects (not dicts)
    node_info = {
        "class_name": "TestNode",
        "full_path": "test.TestNode",
        "source": "builtin",
        "input_specs": [
            PortSpec(name="in1", dtype="float32", shape=[-1], optional=False)
        ],
        "output_specs": [
            PortSpec(name="out1", dtype="int64", shape=[-1], optional=True)
        ]
    }

    mock_parent = MagicMock()
    item = NodePaletteItem(mock_parent, node_info)

    tooltip = item.toolTip(0)

    # Should handle PortSpec objects
    assert "in1" in tooltip
    assert "out1" in tooltip
    assert "float32" in tooltip
    assert "int64" in tooltip


def test_node_palette_with_plugin_source():
    """Test NodePaletteItem with plugin source."""
    node_info = {
        "class_name": "PluginNode",
        "full_path": "my_plugin.PluginNode",
        "source": "plugin",
        "plugin_name": "my_plugin",
        "input_specs": [],
        "output_specs": []
    }

    mock_parent = MagicMock()
    item = NodePaletteItem(mock_parent, node_info)

    tooltip = item.toolTip(0)

    # Should mention plugin name
    assert "my_plugin" in tooltip or "Plugin" in tooltip
