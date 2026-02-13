"""Test script for Pipeline Info dialog functionality.

This script tests the pipeline metadata viewing and editing capabilities:
1. Create a pipeline with initial metadata
2. Open pipeline info dialog
3. Edit metadata fields
4. Verify metadata is updated correctly
"""

import sys

from PySide6.QtWidgets import QApplication

from cuvis_ai_ui.main_window import MainWindow
from cuvis_ai_ui.widgets.pipeline_info_dialog import PipelineInfoDialog


def test_pipeline_info_dialog():
    """Test the pipeline info dialog standalone."""
    _app = QApplication(sys.argv)

    # Test with sample metadata
    sample_metadata = {
        "name": "Test Pipeline",
        "description": "A sample pipeline for testing",
        "tags": ["test", "sample", "demo"],
        "author": "Test User",
        "created": "2026-01-28T16:00:00",
        "custom_field": "custom_value",  # Extra field
    }

    print("=" * 60)
    print("Pipeline Info Dialog Test")
    print("=" * 60)
    print("\nInitial metadata:")
    for key, value in sample_metadata.items():
        print(f"  {key}: {value}")

    # Create and show dialog
    dialog = PipelineInfoDialog(sample_metadata)

    print("\n✓ Dialog created successfully")
    print("✓ Opening dialog...")
    print("\nInstructions:")
    print("  1. Review the metadata fields")
    print("  2. Edit any fields you want")
    print("  3. Click OK to save or Cancel to discard")
    print("=" * 60)

    result = dialog.exec()

    if result:
        updated_metadata = dialog.get_metadata()
        print("\n✓ Dialog accepted (OK clicked)")
        print("\nUpdated metadata:")
        for key, value in updated_metadata.items():
            print(f"  {key}: {value}")

        # Check what changed
        changes = []
        for key in set(sample_metadata.keys()) | set(updated_metadata.keys()):
            old_val = sample_metadata.get(key)
            new_val = updated_metadata.get(key)
            if old_val != new_val:
                changes.append(f"  {key}: {old_val} → {new_val}")

        if changes:
            print("\nChanges detected:")
            for change in changes:
                print(change)
        else:
            print("\nNo changes detected")
    else:
        print("\n✗ Dialog cancelled")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


def test_main_window_integration():
    """Test pipeline info from main window menu."""
    app = QApplication(sys.argv)

    print("=" * 60)
    print("Main Window Integration Test")
    print("=" * 60)
    print("\nCreating main window...")

    window = MainWindow()

    # Set some initial metadata
    window._metadata = {
        "name": "Integration Test Pipeline",
        "description": "Testing from main window",
        "tags": ["integration", "test"],
    }

    print("✓ Main window created")
    print("\nInstructions:")
    print("  1. Use menu: File → Pipeline Info... (or press Ctrl+I)")
    print("  2. Edit the metadata")
    print("  3. Click OK to save")
    print("  4. Notice the window title updates with '*' (unsaved changes)")
    print("  5. Close the window to finish test")
    print("=" * 60)

    window.show()
    app.exec()

    print("\n" + "=" * 60)
    print("Integration test completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Choose test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--dialog":
        # Test dialog only
        test_pipeline_info_dialog()
    else:
        # Test full integration with main window
        test_main_window_integration()
