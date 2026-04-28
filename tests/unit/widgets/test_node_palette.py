"""Unit tests for NodePalette widget."""

from unittest.mock import MagicMock

from cuvis_ai_schemas.enums import NodeCategory, NodeTag
from cuvis_ai_schemas.grpc.conversions import node_category_to_proto, node_tag_to_proto

from cuvis_ai_ui.adapters import NodeRegistry
from cuvis_ai_ui.widgets.node_palette import NodePalette, NodePaletteItem


def _count_visible_items(palette: NodePalette) -> int:
    """Count visible (non-hidden) node items in the tree."""
    count = 0
    for i in range(palette._tree.topLevelItemCount()):
        cat_item = palette._tree.topLevelItem(i)
        if cat_item is None or cat_item.isHidden():
            continue
        for j in range(cat_item.childCount()):
            child = cat_item.child(j)
            if child and not child.isHidden():
                count += 1
    return count


def test_node_palette_item_initialization(sample_node_info):
    """Test NodePaletteItem initialization with node info."""
    mock_parent = MagicMock()

    item = NodePaletteItem(mock_parent, sample_node_info)

    assert item.node_info == sample_node_info
    assert item.text(0) == "MinMaxNormalizer"


def test_node_palette_item_tooltip(sample_node_info):
    """NodePaletteItem tooltip contains port info, category, and tags."""
    mock_parent = MagicMock()

    item = NodePaletteItem(mock_parent, sample_node_info)
    tooltip = item.toolTip(0)

    assert "MinMaxNormalizer" in tooltip
    assert "cube" in tooltip
    assert "float32" in tooltip


def test_node_palette_item_tooltip_includes_category_and_tags(sample_node_info):
    """Tooltip shows Category and Tags lines."""
    mock_parent = MagicMock()

    item = NodePaletteItem(mock_parent, sample_node_info)
    tooltip = item.toolTip(0)

    assert "Category:" in tooltip
    assert "Tags:" in tooltip


def test_node_palette_item_with_empty_specs():
    """NodePaletteItem works with no port specs, category, tags, or icon."""
    node_info = {
        "class_name": "EmptyNode",
        "full_path": "test.EmptyNode",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
    }

    mock_parent = MagicMock()
    item = NodePaletteItem(mock_parent, node_info)

    assert item.text(0) == "EmptyNode"
    tooltip = item.toolTip(0)
    assert "EmptyNode" in tooltip


def test_node_palette_initialization(qapp, node_registry):
    """Test NodePalette widget initialization."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    assert palette is not None
    assert palette._graph == mock_graph


def test_initial_populate_uses_registry_nodes(qapp, node_registry):
    """Palette must have tree items from the registry without calling refresh_nodes."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    # _all_nodes seeded in __init__; tree should already be populated
    assert palette._tree.topLevelItemCount() > 0
    assert len(palette._all_nodes) == len(node_registry.get_all_nodes())


def test_node_palette_populate_with_registry(qapp, node_registry):
    """Palette is populated from NodeRegistry during init."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    assert palette._tree.topLevelItemCount() > 0


def test_node_palette_populate_groups_by_category(qapp):
    """Palette top-level items show NodeCategory.get_display_name() text."""
    mock_graph = MagicMock()
    registry = NodeRegistry()

    registry.register_nodes(
        [
            {
                "class_name": "Loader",
                "full_path": "a.Loader",
                "source": "builtin",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.SOURCE),
                "tags": [],
                "icon_svg": b"",
            },
            {
                "class_name": "Norm",
                "full_path": "a.Norm",
                "source": "builtin",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.TRANSFORM),
                "tags": [],
                "icon_svg": b"",
            },
        ]
    )

    palette = NodePalette(registry, mock_graph)

    section_texts = [
        palette._tree.topLevelItem(i).text(0) for i in range(palette._tree.topLevelItemCount())
    ]
    source_label = NodeCategory.SOURCE.get_display_name()
    transform_label = NodeCategory.TRANSFORM.get_display_name()

    assert any(source_label in t for t in section_texts)
    assert any(transform_label in t for t in section_texts)


def test_node_palette_search_functionality(qapp, node_registry):
    """Search filter hides non-matching nodes."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    initial_visible = _count_visible_items(palette)

    palette._search_input.setText("MinMax")

    filtered_visible = _count_visible_items(palette)

    assert filtered_visible <= initial_visible


def test_node_palette_search_matches_tag_shortlabels(qapp):
    """Searching a tag short-label surfaces nodes carrying that tag."""
    mock_graph = MagicMock()
    registry = NodeRegistry()

    hsi_wire = node_tag_to_proto(NodeTag.HYPERSPECTRAL)

    registry.register_nodes(
        [
            {
                "class_name": "HsiNode",
                "full_path": "a.HsiNode",
                "source": "builtin",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.SOURCE),
                "tags": [hsi_wire],
                "icon_svg": b"",
            },
            {
                "class_name": "RgbNode",
                "full_path": "a.RgbNode",
                "source": "builtin",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.SOURCE),
                "tags": [node_tag_to_proto(NodeTag.RGB)],
                "icon_svg": b"",
            },
        ]
    )

    palette = NodePalette(registry, mock_graph)

    # "hsi" is the short_label for NodeTag.HYPERSPECTRAL
    palette._search_input.setText("hsi")

    assert _count_visible_items(palette) == 1


def test_node_palette_clear_search(qapp, node_registry):
    """Clearing search restores all items."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    initial_visible = _count_visible_items(palette)

    palette._search_input.setText("NonExistent")
    palette._search_input.clear()

    final_visible = _count_visible_items(palette)

    assert final_visible == initial_visible


def test_node_palette_organizes_by_category(qapp):
    """Palette creates multiple sections when nodes span multiple categories."""
    mock_graph = MagicMock()
    registry = NodeRegistry()

    registry.register_nodes(
        [
            {
                "class_name": "MinMaxNormalizer",
                "full_path": "cuvis_ai.node.normalization.MinMaxNormalizer",
                "source": "builtin",
                "plugin_name": "",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.TRANSFORM),
                "tags": [],
                "icon_svg": b"",
            },
            {
                "class_name": "SimpleModel",
                "full_path": "cuvis_ai.node.model.SimpleModel",
                "source": "builtin",
                "plugin_name": "",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.MODEL),
                "tags": [],
                "icon_svg": b"",
            },
            {
                "class_name": "DataLoader",
                "full_path": "cuvis_ai.node.data.DataLoader",
                "source": "builtin",
                "plugin_name": "",
                "input_specs": [],
                "output_specs": [],
                "category": node_category_to_proto(NodeCategory.SOURCE),
                "tags": [],
                "icon_svg": b"",
            },
        ]
    )

    palette = NodePalette(registry, mock_graph)

    assert palette._tree.topLevelItemCount() > 1


def test_node_palette_refresh(qapp, node_registry):
    """Refreshing the palette keeps the same section count."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    initial_count = palette._tree.topLevelItemCount()

    palette._populate_tree()

    assert palette._tree.topLevelItemCount() == initial_count


def test_node_palette_empty_registry(qapp):
    """Palette with empty NodeRegistry does not crash."""
    mock_graph = MagicMock()

    empty_registry = NodeRegistry()

    palette = NodePalette(empty_registry, mock_graph)

    assert palette._tree.topLevelItemCount() == 0


def test_node_palette_item_selection(qapp, node_registry):
    """Selecting a tree item works without error."""
    mock_graph = MagicMock()

    palette = NodePalette(node_registry, mock_graph)

    if palette._tree.topLevelItemCount() > 0:
        category_item = palette._tree.topLevelItem(0)
        if category_item.childCount() > 0:
            node_item = category_item.child(0)

            palette._tree.setCurrentItem(node_item)

            assert palette._tree.currentItem() == node_item


def test_node_palette_port_spec_in_tooltip():
    """Dict-format port specs render in tooltip."""
    node_info = {
        "class_name": "TestNode",
        "full_path": "test.TestNode",
        "source": "builtin",
        "input_specs": [{"name": "in1", "dtype": "float32", "shape": "[-1]", "optional": False}],
        "output_specs": [{"name": "out1", "dtype": "int64", "shape": "[-1]", "optional": True}],
    }

    mock_parent = MagicMock()
    item = NodePaletteItem(mock_parent, node_info)

    tooltip = item.toolTip(0)

    assert "in1" in tooltip
    assert "out1" in tooltip
    assert "float32" in tooltip
    assert "int64" in tooltip


def test_node_palette_with_plugin_source():
    """NodePaletteItem with plugin source mentions the plugin name in the tooltip."""
    node_info = {
        "class_name": "PluginNode",
        "full_path": "my_plugin.PluginNode",
        "source": "plugin",
        "plugin_name": "my_plugin",
        "input_specs": [],
        "output_specs": [],
    }

    mock_parent = MagicMock()
    item = NodePaletteItem(mock_parent, node_info)

    tooltip = item.toolTip(0)

    assert "my_plugin" in tooltip or "Plugin" in tooltip
