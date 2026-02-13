"""Adapters for cuvis-ai to NodeGraphQt integration.

This package provides:
- PortMapper: Port specification and color mapping
- NodeAdapter: Wraps cuvis-ai nodes as NodeGraphQt nodes
- PipelineSerializer: Bidirectional YAML <-> NodeGraphQt conversion
- NodeIntrospector: Extract port specs from cuvis-ai classes
"""

from .node_adapter import CuvisNodeAdapter, NodeRegistry, create_node_class
from .node_introspector import enrich_node_info, enrich_node_list
from .pipeline_serializer import PipelineSerializer
from cuvis_ai_schemas.extensions.ui import DTYPE_COLORS, PortDisplaySpec
from cuvis_ai_schemas.pipeline.ports import PortSpec

from .port_helpers import (
    create_input_port,
    create_output_port,
    format_port_tooltip,
    get_port_spec,
    validate_connection,
)

__all__ = [
    # Port mapper
    "PortSpec",
    "DTYPE_COLORS",
    "PortDisplaySpec",
    "create_input_port",
    "create_output_port",
    "get_port_spec",
    "validate_connection",
    "format_port_tooltip",
    # Node adapter
    "CuvisNodeAdapter",
    "NodeRegistry",
    "create_node_class",
    # Pipeline serializer
    "PipelineSerializer",
    # Node introspection
    "enrich_node_info",
    "enrich_node_list",
]
