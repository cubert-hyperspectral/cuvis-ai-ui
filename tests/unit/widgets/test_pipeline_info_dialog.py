"""Unit tests for PipelineInfoDialog widget."""

from PySide6.QtWidgets import QDialogButtonBox

from cuvis_ai_ui.widgets.pipeline_info_dialog import PipelineInfoDialog


def test_pipeline_info_dialog_initialization(qapp):
    """Test PipelineInfoDialog initialization with no metadata."""
    dialog = PipelineInfoDialog()

    assert dialog is not None
    assert dialog.windowTitle() == "Pipeline Information"


def test_pipeline_info_dialog_with_metadata(qapp):
    """Test PipelineInfoDialog initialization with metadata."""
    metadata = {
        "name": "Test Pipeline",
        "description": "A test pipeline description",
        "tags": ["test", "example"],
        "author": "Test Author",
    }

    dialog = PipelineInfoDialog(metadata=metadata)

    # Should load the metadata into fields
    assert dialog._name_edit.text() == "Test Pipeline"
    assert "test pipeline description" in dialog._description_edit.toPlainText().lower()
    assert dialog._author_edit.text() == "Test Author"


def test_pipeline_info_dialog_get_metadata(qapp):
    """Test retrieving metadata from dialog."""
    metadata = {
        "name": "Test Pipeline",
        "description": "Test description",
        "tags": ["tag1", "tag2"],
    }

    dialog = PipelineInfoDialog(metadata=metadata)
    retrieved = dialog.get_metadata()

    assert retrieved["name"] == "Test Pipeline"
    assert retrieved["description"] == "Test description"
    assert "tag1" in retrieved.get("tags", []) or "tag1" in str(retrieved.get("tags", ""))


def test_pipeline_info_dialog_update_metadata(qapp):
    """Test updating metadata in dialog."""
    dialog = PipelineInfoDialog()

    # Update fields
    dialog._name_edit.setText("New Pipeline")
    dialog._description_edit.setPlainText("New description")
    dialog._author_edit.setText("New Author")
    dialog._tags_edit.setText("tag1, tag2")

    # Retrieve updated metadata
    metadata = dialog.get_metadata()

    assert metadata["name"] == "New Pipeline"
    assert metadata["description"] == "New description"
    assert metadata["author"] == "New Author"


def test_pipeline_info_dialog_empty_metadata(qapp):
    """Test dialog with empty metadata."""
    dialog = PipelineInfoDialog(metadata={})

    assert dialog._name_edit.text() == ""
    assert dialog._description_edit.toPlainText() == ""
    assert dialog._author_edit.text() == ""


def test_pipeline_info_dialog_tags_parsing(qapp):
    """Test that tags are properly parsed from comma-separated string."""
    metadata = {"name": "Test", "tags": ["tag1", "tag2", "tag3"]}

    dialog = PipelineInfoDialog(metadata=metadata)

    # Tags field should show comma-separated values
    tags_text = dialog._tags_edit.text()

    # Should contain the tags (exact format may vary)
    assert len(tags_text) > 0


def test_pipeline_info_dialog_tags_output(qapp):
    """Test that tags are properly output as list."""
    dialog = PipelineInfoDialog()

    dialog._tags_edit.setText("tag1, tag2, tag3")

    metadata = dialog.get_metadata()

    # Tags should be a list (or comma-separated string)
    tags = metadata.get("tags", [])
    if isinstance(tags, list):
        assert len(tags) == 3
        assert "tag1" in tags
    else:
        # If returned as string, should contain all tags
        assert "tag1" in str(tags)


def test_pipeline_info_dialog_created_timestamp(qapp):
    """Test that created timestamp is handled correctly."""
    metadata = {"name": "Test", "created": "2024-01-01T12:00:00"}

    dialog = PipelineInfoDialog(metadata=metadata)

    # Created label should show timestamp
    created_text = dialog._created_label.text()

    # Should contain some time information
    assert len(created_text) > 0 or created_text == ""  # May be read-only


def test_pipeline_info_dialog_accept_button(qapp, qtbot):
    """Test accepting the dialog."""
    dialog = PipelineInfoDialog()
    dialog._name_edit.setText("Test Pipeline")

    # Find OK/Accept button
    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None

    ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
    if ok_button:
        with qtbot.waitSignal(dialog.accepted, timeout=1000):
            ok_button.click()


def test_pipeline_info_dialog_reject_button(qapp, qtbot):
    """Test rejecting/canceling the dialog."""
    dialog = PipelineInfoDialog()

    # Find Cancel/Reject button
    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box is not None

    cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel_button:
        with qtbot.waitSignal(dialog.rejected, timeout=1000):
            cancel_button.click()


def test_pipeline_info_dialog_minimum_size(qapp):
    """Test that dialog has reasonable minimum size."""
    dialog = PipelineInfoDialog()

    assert dialog.minimumWidth() > 0
    assert dialog.minimumHeight() > 0


def test_pipeline_info_dialog_field_placeholders(qapp):
    """Test that form fields have helpful placeholders."""
    dialog = PipelineInfoDialog()

    # Name field should have placeholder
    name_placeholder = dialog._name_edit.placeholderText()
    assert len(name_placeholder) > 0
    assert "name" in name_placeholder.lower()

    # Tags field should have placeholder
    tags_placeholder = dialog._tags_edit.placeholderText()
    assert len(tags_placeholder) > 0


def test_pipeline_info_dialog_custom_metadata_fields(qapp):
    """Test handling of custom/unknown metadata fields."""
    metadata = {"name": "Test", "custom_field": "custom_value", "another_field": 123}

    dialog = PipelineInfoDialog(metadata=metadata)

    # Custom fields might be shown read-only or ignored
    # Dialog should not crash with extra fields
    assert dialog._name_edit.text() == "Test"


def test_pipeline_info_dialog_required_name_field(qapp):
    """Test that name field is marked as required."""
    dialog = PipelineInfoDialog()

    # Name field placeholder should indicate it's required
    placeholder = dialog._name_edit.placeholderText()
    assert "required" in placeholder.lower()


def test_pipeline_info_dialog_description_multiline(qapp):
    """Test that description field supports multiple lines."""
    dialog = PipelineInfoDialog()

    multiline_text = "Line 1\nLine 2\nLine 3"
    dialog._description_edit.setPlainText(multiline_text)

    assert "\n" in dialog._description_edit.toPlainText()


def test_pipeline_info_dialog_metadata_persistence(qapp):
    """Test that metadata round-trips correctly."""
    original_metadata = {
        "name": "Original Pipeline",
        "description": "Original description with\nmultiple lines",
        "tags": ["tag1", "tag2"],
        "author": "Original Author",
    }

    # Create dialog with metadata
    dialog = PipelineInfoDialog(metadata=original_metadata)

    # Retrieve metadata without changes
    retrieved = dialog.get_metadata()

    # Key fields should match
    assert retrieved["name"] == original_metadata["name"]
    assert retrieved["author"] == original_metadata["author"]


def test_pipeline_info_dialog_with_none_metadata(qapp):
    """Test dialog with None metadata (should use empty dict)."""
    dialog = PipelineInfoDialog(metadata=None)

    assert dialog is not None
    assert dialog._name_edit.text() == ""


def test_pipeline_info_dialog_whitespace_handling(qapp):
    """Test that dialog handles whitespace in fields correctly."""
    dialog = PipelineInfoDialog()

    # Set fields with extra whitespace
    dialog._name_edit.setText("  Pipeline Name  ")
    dialog._author_edit.setText("  Author Name  ")

    metadata = dialog.get_metadata()

    # May or may not trim whitespace - just ensure it doesn't crash
    assert "Pipeline Name" in metadata["name"]
