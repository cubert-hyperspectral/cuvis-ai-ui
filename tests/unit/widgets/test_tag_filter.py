"""Unit tests for TagFilterWidget filter logic."""


from cuvis_ai_schemas.enums import NodeTag
from cuvis_ai_schemas.grpc.conversions import node_tag_to_proto

from cuvis_ai_ui.widgets.tag_filter import TagFilterWidget


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
    """Empty active_tags dict → all nodes returned unchanged."""
    nodes = [_node([NodeTag.HYPERSPECTRAL]), _node([NodeTag.RGB]), _node([])]

    result = TagFilterWidget.filter_nodes(nodes, {})

    assert result is nodes


def test_filter_nodes_or_within_namespace():
    """Within a namespace, a node passes if it carries *any* active tag."""
    hsi = _node([NodeTag.HYPERSPECTRAL])
    rgb = _node([NodeTag.RGB])
    no_tags = _node([])

    active = {"Modality": {NodeTag.HYPERSPECTRAL, NodeTag.RGB}, "Task": set()}

    result = TagFilterWidget.filter_nodes([hsi, rgb, no_tags], active)

    assert hsi in result
    assert rgb in result
    assert no_tags not in result


def test_filter_nodes_and_across_namespaces():
    """A node must satisfy *every* namespace that has active selections."""
    hsi_seg = _node([NodeTag.HYPERSPECTRAL, NodeTag.SEGMENTATION])
    hsi_only = _node([NodeTag.HYPERSPECTRAL])
    seg_only = _node([NodeTag.SEGMENTATION])

    active = {
        "Modality": {NodeTag.HYPERSPECTRAL},
        "Task": {NodeTag.SEGMENTATION},
    }

    result = TagFilterWidget.filter_nodes([hsi_seg, hsi_only, seg_only], active)

    assert hsi_seg in result
    assert hsi_only not in result
    assert seg_only not in result


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

    active = {"Modality": {NodeTag.HYPERSPECTRAL}}

    result = TagFilterWidget.filter_nodes([node_with_unknown], active)

    assert node_with_unknown not in result


def test_filter_nodes_empty_namespace_does_not_block():
    """A namespace with an empty active set does not filter anything out."""
    hsi = _node([NodeTag.HYPERSPECTRAL])

    # Task namespace is active but empty → should not block hsi
    active = {"Modality": {NodeTag.HYPERSPECTRAL}, "Task": set()}

    result = TagFilterWidget.filter_nodes([hsi], active)

    assert hsi in result


def test_filter_nodes_node_with_no_tags_filtered_when_namespace_active():
    """A node with no tags is excluded when any namespace has active selections."""
    no_tags = _node([])

    active = {"Modality": {NodeTag.HYPERSPECTRAL}}

    result = TagFilterWidget.filter_nodes([no_tags], active)

    assert no_tags not in result
