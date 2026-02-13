"""Qt widgets for cuvis-ai visualization.

This package provides:
- NodePalette: Searchable tree widget for node selection
- PropertyEditor: Dynamic form for editing node hyperparameters
- PluginManagerDialog: Dialog for loading/managing plugins
- SessionDialog: Dialog for session management
- PipelineInfoDialog: Dialog for viewing/editing pipeline metadata
- ConnectionDialog: Dialog for server connection settings
"""

from .connection_dialog import ConnectionDialog
from .node_palette import NodePalette
from .pipeline_info_dialog import PipelineInfoDialog
from .plugin_manager import PluginManagerDialog, SessionDialog
from .property_editor import ExecutionStagesEditor, PropertyEditor

__all__ = [
    "ConnectionDialog",
    "NodePalette",
    "PropertyEditor",
    "ExecutionStagesEditor",
    "PluginManagerDialog",
    "SessionDialog",
    "PipelineInfoDialog",
]
