"""Unit tests for TagSearchFilter.filter_nodes.

Filter contract: OR within tag namespace, AND across namespaces. The widget
takes a flat ``set[NodeTag]`` and re-buckets internally — these tests exercise
that bucketing.
"""

from unittest.mock import MagicMock

from cuvis_ai_schemas.enums import NodeTag
from cuvis_ai_schemas.grpc.conversions import node_tag_to_proto

from cuvis_ai_ui.widgets.tag_search_filter import TagSearchFilter, _Chip


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


# ---------------------------------------------------------------------------
# Chip widget + completer wiring
# ---------------------------------------------------------------------------


def test_chip_invokes_on_remove_when_clicked(qapp):
    """Clicking a _Chip fires its on_remove callback with the bound NodeTag."""
    callback = MagicMock()

    chip = _Chip(NodeTag.HYPERSPECTRAL, on_remove=callback)
    chip.click()

    callback.assert_called_once_with(NodeTag.HYPERSPECTRAL)
    assert chip.tag is NodeTag.HYPERSPECTRAL


def test_chip_text_contains_remove_marker(qapp):
    """Chip label is '<short_label>  ×' so users see the close affordance."""
    chip = _Chip(NodeTag.SEGMENTATION, on_remove=lambda _t: None)

    assert "×" in chip.text()


def test_completer_activated_adds_chip_and_emits_signal(qtbot, qapp):
    """Picking a completer entry adds an active tag, chip, and emits."""
    widget = TagSearchFilter()

    with qtbot.waitSignal(widget.tags_changed, timeout=1000) as blocker:
        widget._on_completer_activated("hsi")

    assert blocker.args == [{NodeTag.HYPERSPECTRAL}]
    assert NodeTag.HYPERSPECTRAL in widget.current_tags()
    # Parent widget is never shown in tests, so check the explicit-hide flag.
    assert not widget._chips_row.isHidden()
    assert widget._input.text() == ""


def test_completer_activated_skips_duplicate(qapp):
    """Re-activating a tag that's already in the chip row is a no-op."""
    widget = TagSearchFilter()
    widget._on_completer_activated("hsi")

    before = widget.current_tags()
    widget._on_completer_activated("hsi")

    assert widget.current_tags() == before
    # Chip count should be unchanged: one chip in the row.
    assert len(widget._chips) == 1


def test_completer_activated_unknown_text_clears_input_only(qapp):
    """An unknown completer string clears the input but doesn't add a chip."""
    widget = TagSearchFilter()
    widget._input.setText("nonsense")

    widget._on_completer_activated("nonsense")

    assert widget.current_tags() == set()
    assert widget._input.text() == ""
    assert widget._chips_row.isHidden()


def test_clear_tags_removes_all_chips_and_emits(qtbot, qapp):
    """clear_tags() drops every chip, hides the row, and emits the empty set."""
    widget = TagSearchFilter()
    widget._on_completer_activated("hsi")
    widget._on_completer_activated("seg")
    assert len(widget._chips) == 2

    with qtbot.waitSignal(widget.tags_changed, timeout=1000) as blocker:
        widget.clear_tags()

    assert blocker.args == [set()]
    assert widget.current_tags() == set()
    assert widget._chips == {}
    assert widget._chips_row.isHidden()


def test_clear_tags_noop_when_empty(qapp):
    """clear_tags() when no tags are active is a no-op (no signal needed)."""
    widget = TagSearchFilter()
    # Should not raise or alter state.
    widget.clear_tags()
    assert widget.current_tags() == set()


def test_chip_removed_via_callback_updates_state(qtbot, qapp):
    """Clicking a chip's × removes it from the active set and emits."""
    widget = TagSearchFilter()
    widget._on_completer_activated("hsi")
    widget._on_completer_activated("seg")

    with qtbot.waitSignal(widget.tags_changed, timeout=1000) as blocker:
        # Simulate the chip-click path by invoking the same callback the chip uses.
        widget._on_chip_removed(NodeTag.HYPERSPECTRAL)

    assert blocker.args == [{NodeTag.SEGMENTATION}]
    assert NodeTag.HYPERSPECTRAL not in widget.current_tags()
    # Row stays "shown" (not hidden) because one chip remains.
    assert not widget._chips_row.isHidden()
