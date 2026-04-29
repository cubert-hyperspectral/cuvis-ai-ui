"""Unit tests for TagSearchFilter.filter_nodes.

Filter contract: OR within tag namespace, AND across namespaces. The widget
takes a flat ``set[NodeTag]`` and re-buckets internally — these tests exercise
that bucketing.
"""

from cuvis_ai_schemas.enums import NodeTag
from cuvis_ai_schemas.grpc.conversions import node_tag_to_proto

from cuvis_ai_ui.widgets.tag_search_filter import TagSearchFilter


def _node(tags: list[NodeTag]) -> dict:
    return {
        "class_name": "N",
        "full_path": "a.N",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [node_tag_to_proto(t) for t in tags],
        "icon_svg": b"",
    }


def test_filter_nodes_no_active_tags_returns_all():
    """Empty active_tags set → all nodes returned unchanged."""
    nodes = [_node([NodeTag.HYPERSPECTRAL]), _node([NodeTag.RGB]), _node([])]

    result = TagSearchFilter.filter_nodes(nodes, set())

    assert result is nodes


def test_filter_nodes_or_within_namespace():
    """Two tags from the same namespace → node passes if it carries either."""
    hsi = _node([NodeTag.HYPERSPECTRAL])
    rgb = _node([NodeTag.RGB])
    no_tags = _node([])

    active = {NodeTag.HYPERSPECTRAL, NodeTag.RGB}  # both are Modality

    result = TagSearchFilter.filter_nodes([hsi, rgb, no_tags], active)

    assert hsi in result
    assert rgb in result
    assert no_tags not in result


def test_filter_nodes_and_across_namespaces():
    """Tags from different namespaces → node must satisfy every namespace."""
    hsi_seg = _node([NodeTag.HYPERSPECTRAL, NodeTag.SEGMENTATION])
    hsi_only = _node([NodeTag.HYPERSPECTRAL])
    seg_only = _node([NodeTag.SEGMENTATION])

    active = {NodeTag.HYPERSPECTRAL, NodeTag.SEGMENTATION}  # Modality + Task

    result = TagSearchFilter.filter_nodes([hsi_seg, hsi_only, seg_only], active)

    assert hsi_seg in result
    assert hsi_only not in result
    assert seg_only not in result


def test_filter_nodes_or_and_combined():
    """OR within Modality, AND with Task: (HSI or MSI) and SEG."""
    hsi_seg = _node([NodeTag.HYPERSPECTRAL, NodeTag.SEGMENTATION])
    msi_seg = _node([NodeTag.MULTISPECTRAL, NodeTag.SEGMENTATION])
    rgb_seg = _node([NodeTag.RGB, NodeTag.SEGMENTATION])
    hsi_class = _node([NodeTag.HYPERSPECTRAL, NodeTag.CLASSIFICATION])

    active = {NodeTag.HYPERSPECTRAL, NodeTag.MULTISPECTRAL, NodeTag.SEGMENTATION}

    result = TagSearchFilter.filter_nodes([hsi_seg, msi_seg, rgb_seg, hsi_class], active)

    assert hsi_seg in result
    assert msi_seg in result
    assert rgb_seg not in result
    assert hsi_class not in result


def test_filter_nodes_unknown_tag_int_dropped_silently():
    """Unknown tag ints (from a newer server) are treated as having no tags."""
    node_with_unknown = {
        "class_name": "N",
        "full_path": "a.N",
        "source": "builtin",
        "input_specs": [],
        "output_specs": [],
        "category": 0,
        "tags": [99999],  # not a known NodeTag wire value
        "icon_svg": b"",
    }

    active = {NodeTag.HYPERSPECTRAL}

    result = TagSearchFilter.filter_nodes([node_with_unknown], active)

    assert node_with_unknown not in result


def test_filter_nodes_node_with_no_tags_filtered_when_active():
    """A node with no tags is excluded as soon as any tag is active."""
    no_tags = _node([])

    active = {NodeTag.HYPERSPECTRAL}

    result = TagSearchFilter.filter_nodes([no_tags], active)

    assert no_tags not in result
