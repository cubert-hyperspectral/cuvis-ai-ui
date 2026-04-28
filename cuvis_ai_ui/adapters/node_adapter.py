"""Node adapter for wrapping cuvis-ai nodes as NodeGraphQt nodes.

This module provides CuvisNodeAdapter - a NodeGraphQt BaseNode subclass
that wraps cuvis-ai node information for visual editing.
"""

from typing import Any

from NodeGraphQt import BaseNode

from cuvis_ai_schemas.enums import NodeCategory, NodeTag
from cuvis_ai_schemas.extensions.ui.node_display import CATEGORY_STYLES, TAG_STYLES
from cuvis_ai_schemas.grpc.conversions import proto_to_node_category, proto_to_node_tag
from cuvis_ai_schemas.pipeline.ports import PortSpec

from .port_helpers import create_input_port, create_output_port


DEFAULT_NODE_COLOR = (100, 100, 100, 255)  # fallback for NodeCategory.UNSPECIFIED


def category_color(category: NodeCategory) -> tuple[int, int, int, int]:
    """Return RGBA from the canonical CATEGORY_STYLES border hex for *category*."""
    styles = CATEGORY_STYLES.get(category, CATEGORY_STYLES[NodeCategory.UNSPECIFIED])
    h = styles["border"]
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255)


def tag_chip_color(tag: NodeTag) -> tuple[int, int, int, int]:
    """Return RGBA from the canonical TAG_STYLES badge_color hex for *tag*."""
    h = TAG_STYLES.get(tag, {}).get("badge_color", "#888888")
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 200)


class CuvisNodeAdapter(BaseNode):
    """NodeGraphQt adapter for cuvis-ai nodes.

    This class wraps cuvis-ai node information (class path, hparams,
    port specs) and presents it as a visual node in NodeGraphQt.

    Attributes:
        __identifier__: Unique node type identifier
        NODE_NAME: Display name for the node
    """

    # NodeGraphQt requires these class attributes
    __identifier__ = "cuvis_ai"
    NODE_NAME = "CuvisNode"

    def __init__(self) -> None:
        """Initialize the node adapter."""
        super().__init__()

        # cuvis-ai specific attributes
        self._cuvis_class_path: str = ""
        self._cuvis_class_name: str = ""
        self._cuvis_source: str = "builtin"
        self._cuvis_plugin_name: str = ""
        self._cuvis_hparams: dict[str, Any] = {}
        self._cuvis_execution_stages: set[str] = {"always"}
        self._cuvis_input_specs: dict[str, PortSpec] = {}
        self._cuvis_output_specs: dict[str, PortSpec] = {}
        self._cuvis_category: NodeCategory = NodeCategory.UNSPECIFIED
        self._cuvis_tags: list[int] = []  # raw proto wire ints; narrowed to NodeTag at the accessor
        self._cuvis_icon_svg: bytes = b""

    @property
    def cuvis_class_path(self) -> str:
        """Full import path of the cuvis-ai node class."""
        return self._cuvis_class_path

    @property
    def cuvis_class_name(self) -> str:
        """Short class name of the cuvis-ai node."""
        return self._cuvis_class_name

    @property
    def cuvis_source(self) -> str:
        """Source of the node (builtin/plugin)."""
        return self._cuvis_source

    @property
    def cuvis_plugin_name(self) -> str:
        """Plugin name if this is a plugin node."""
        return self._cuvis_plugin_name

    @property
    def cuvis_hparams(self) -> dict[str, Any]:
        """Hyperparameters for this node instance."""
        return self._cuvis_hparams

    @cuvis_hparams.setter
    def cuvis_hparams(self, value: dict[str, Any]) -> None:
        """Set hyperparameters."""
        self._cuvis_hparams = value

    @property
    def cuvis_execution_stages(self) -> set[str]:
        """Execution stages this node runs in."""
        return self._cuvis_execution_stages

    @cuvis_execution_stages.setter
    def cuvis_execution_stages(self, value: set[str]) -> None:
        """Set execution stages."""
        self._cuvis_execution_stages = value

    @property
    def cuvis_input_specs(self) -> dict[str, PortSpec]:
        """Input port specifications."""
        return self._cuvis_input_specs

    @property
    def cuvis_output_specs(self) -> dict[str, PortSpec]:
        """Output port specifications."""
        return self._cuvis_output_specs

    @property
    def cuvis_category(self) -> NodeCategory:
        """NodeCategory derived from the proto wire field."""
        return self._cuvis_category

    @property
    def cuvis_tags(self) -> list[NodeTag]:
        """Known NodeTag members; unknown wire ints from a newer server are dropped silently."""
        out: list[NodeTag] = []
        for raw in self._cuvis_tags:
            tag = proto_to_node_tag(raw)
            if tag is not None:
                out.append(tag)
        return out

    @property
    def cuvis_icon_svg(self) -> bytes:
        """Raw SVG bytes for the node icon; b'' when absent."""
        return self._cuvis_icon_svg

    def configure_from_node_info(self, node_info: dict[str, Any]) -> None:
        """Configure this adapter from node info returned by gRPC.

        Args:
            node_info: Dictionary containing:
                - class_name: Short class name
                - full_path: Full import path
                - source: "builtin" or "plugin"
                - plugin_name: Plugin name (if plugin source)
                - input_specs: List of input port specs
                - output_specs: List of output port specs
                - hparams: Default hyperparameters
                - category: NodeCategory proto wire int (0 = UNSPECIFIED)
                - tags: list of NodeTag proto wire ints
                - icon_svg: SVG bytes (b"" when absent)
        """
        self._cuvis_class_name = node_info.get("class_name", "Unknown")
        self._cuvis_class_path = node_info.get("full_path", "")
        self._cuvis_source = node_info.get("source", "builtin")
        self._cuvis_plugin_name = node_info.get("plugin_name", "")
        self._cuvis_hparams = node_info.get("hparams", {})
        self._cuvis_category = proto_to_node_category(node_info.get("category", 0))
        self._cuvis_tags = list(node_info.get("tags", []))
        self._cuvis_icon_svg = node_info.get("icon_svg", b"")

        # Set node display name
        self.set_name(self._cuvis_class_name)

        # Colour from schemas CATEGORY_STYLES; only RGB accepted by NodeGraphQt
        r, g, b, _ = category_color(self._cuvis_category)
        self.set_color(r, g, b)

        # Create input ports
        for spec_data in node_info.get("input_specs", []):
            if isinstance(spec_data, dict):
                # Extract port name separately - PortSpec doesn't have a name field
                port_name = spec_data.get("name", "unknown")
                # Create PortSpec with only the fields it supports
                shape_data = spec_data.get("shape", [])
                if isinstance(shape_data, list):
                    shape = tuple(shape_data)
                elif isinstance(shape_data, str):
                    # Parse string representation like "[-1, -1]"
                    shape = tuple(
                        int(x.strip()) if x.strip().lstrip("-").isdigit() else x.strip()
                        for x in shape_data.strip("[]").split(",")
                        if x.strip()
                    )
                else:
                    shape = shape_data if isinstance(shape_data, tuple) else ()

                spec = PortSpec(
                    dtype=spec_data.get("dtype", "any"),
                    shape=shape,
                    description=spec_data.get("description", ""),
                    optional=spec_data.get("optional", False),
                )
            else:
                # Already a PortSpec object, need to get name from context
                port_name = "unknown"
                spec = spec_data

            self._cuvis_input_specs[port_name] = spec
            create_input_port(self, port_name, spec)

        # Create output ports
        for spec_data in node_info.get("output_specs", []):
            if isinstance(spec_data, dict):
                # Extract port name separately - PortSpec doesn't have a name field
                port_name = spec_data.get("name", "unknown")
                # Create PortSpec with only the fields it supports
                shape_data = spec_data.get("shape", [])
                if isinstance(shape_data, list):
                    shape = tuple(shape_data)
                elif isinstance(shape_data, str):
                    # Parse string representation like "[-1, -1]"
                    shape = tuple(
                        int(x.strip()) if x.strip().lstrip("-").isdigit() else x.strip()
                        for x in shape_data.strip("[]").split(",")
                        if x.strip()
                    )
                else:
                    shape = shape_data if isinstance(shape_data, tuple) else ()

                spec = PortSpec(
                    dtype=spec_data.get("dtype", "any"),
                    shape=shape,
                    description=spec_data.get("description", ""),
                    optional=spec_data.get("optional", False),
                )
            else:
                # Already a PortSpec object, need to get name from context
                port_name = "unknown"
                spec = spec_data

            self._cuvis_output_specs[port_name] = spec
            create_output_port(self, port_name, spec)

    def get_cuvis_config(self) -> dict[str, Any]:
        """Export this node's configuration for YAML serialization.

        Returns:
            Dictionary in cuvis-ai pipeline YAML format:
            {
                "class_name": "full.path.to.NodeClass",
                "name": "node_instance_name",
                "params": {...}
            }
        """
        config: dict[str, Any] = {
            "class_name": self._cuvis_class_path,
            "name": self.name(),
        }

        if self._cuvis_hparams:
            config["hparams"] = self._cuvis_hparams

        if self._cuvis_execution_stages != {"always"}:
            config["execution_stages"] = list(self._cuvis_execution_stages)

        return config

    def update_hparam(self, key: str, value: Any) -> None:
        """Update a single hyperparameter.

        Args:
            key: Parameter name
            value: New value
        """
        self._cuvis_hparams[key] = value

    def get_hparam(self, key: str, default: Any = None) -> Any:
        """Get a hyperparameter value.

        Args:
            key: Parameter name
            default: Default value if not found

        Returns:
            Parameter value or default
        """
        return self._cuvis_hparams.get(key, default)


def create_node_class(node_info: dict[str, Any]) -> type[BaseNode]:
    """Dynamically create a NodeGraphQt node class for a cuvis-ai node.

    NodeGraphQt requires unique node classes for the node palette.
    This function creates a subclass of CuvisNodeAdapter with the
    proper identifier and name for each cuvis-ai node type.

    Args:
        node_info: Node information dictionary

    Returns:
        A new subclass of CuvisNodeAdapter
    """
    class_name = node_info.get("class_name", "Unknown")
    full_path = node_info.get("full_path", "")

    # Create identifier from full path (dots to underscores)
    # NodeGraphQt uses: __identifier__ + "." + NODE_NAME
    # So for full_path "cuvis_ai.node.data.LentilsAnomalyDataNode",
    # we want identifier "cuvis_ai_node_data_LentilsAnomalyDataNode"
    identifier = full_path.replace(".", "_")

    # Create the node class dynamically
    node_class = type(
        f"Cuvis_{class_name}",
        (CuvisNodeAdapter,),
        {
            "__identifier__": identifier,  # Already includes full path as underscores
            "NODE_NAME": class_name,
            "_node_info": node_info,
        },
    )

    # Override __init__ to auto-configure
    original_init = node_class.__init__

    def new_init(self: CuvisNodeAdapter) -> None:
        original_init(self)
        self.configure_from_node_info(node_info)

    node_class.__init__ = new_init  # type: ignore

    return node_class


class NodeRegistry:
    """Registry of available cuvis-ai node types.

    Manages the mapping from class paths to NodeGraphQt node classes.
    Used by the node palette for drag-and-drop creation.
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._nodes: dict[str, dict[str, Any]] = {}
        self._node_classes: dict[str, type[BaseNode]] = {}

    def register_node(self, node_info: dict[str, Any]) -> None:
        """Register a node type.

        Args:
            node_info: Node information from gRPC
        """
        full_path = node_info.get("full_path", "")
        if not full_path:
            return

        self._nodes[full_path] = node_info
        self._node_classes[full_path] = create_node_class(node_info)

    def register_nodes(self, nodes: list[dict[str, Any]]) -> None:
        """Register multiple node types.

        Args:
            nodes: List of node info dictionaries
        """
        for node_info in nodes:
            self.register_node(node_info)

    def get_node_info(self, class_path: str) -> dict[str, Any] | None:
        """Get node info by class path.

        Args:
            class_path: Full class import path

        Returns:
            Node info dictionary or None
        """
        return self._nodes.get(class_path)

    def get_node_class(self, class_path: str) -> type[BaseNode] | None:
        """Get NodeGraphQt node class by class path.

        Args:
            class_path: Full class import path

        Returns:
            Node class or None
        """
        return self._node_classes.get(class_path)

    def get_all_nodes(self) -> list[dict[str, Any]]:
        """Get all registered node infos.

        Returns:
            List of all node info dictionaries
        """
        return list(self._nodes.values())

    def get_nodes_by_source(self, source: str) -> list[dict[str, Any]]:
        """Get nodes filtered by source.

        Args:
            source: "builtin" or "plugin"

        Returns:
            List of matching node info dictionaries
        """
        return [info for info in self._nodes.values() if info.get("source") == source]

    def get_nodes_by_plugin(self, plugin_name: str) -> list[dict[str, Any]]:
        """Get nodes from a specific plugin.

        Args:
            plugin_name: Plugin identifier

        Returns:
            List of matching node info dictionaries
        """
        return [info for info in self._nodes.values() if info.get("plugin_name") == plugin_name]

    def group_by_category(
        self, nodes: list[dict[str, Any]] | None = None
    ) -> dict[NodeCategory, list[dict[str, Any]]]:
        """Group nodes by NodeCategory.

        Args:
            nodes: Subset to group. Defaults to all registered nodes.

        Returns:
            Dict keyed by NodeCategory; categories with zero nodes are absent.
        """
        source = nodes if nodes is not None else list(self._nodes.values())
        result: dict[NodeCategory, list[dict[str, Any]]] = {}
        for info in source:
            cat = proto_to_node_category(info.get("category", 0))
            result.setdefault(cat, []).append(info)
        return result

    def register_with_graph(self, graph: Any) -> int:
        """Register all node classes with a NodeGraphQt graph.

        This must be called before nodes can be created via graph.create_node().

        Args:
            graph: NodeGraphQt NodeGraph instance

        Returns:
            Number of node classes registered
        """
        from loguru import logger

        count = 0
        for class_path, node_class in self._node_classes.items():
            try:
                graph.register_node(node_class)
                count += 1
            except Exception as e:
                # Log registration failures for debugging
                logger.debug(f"Failed to register {class_path}: {e}")
        return count

    def clear(self) -> None:
        """Clear all registered nodes."""
        self._nodes.clear()
        self._node_classes.clear()

    def __len__(self) -> int:
        """Return number of registered nodes."""
        return len(self._nodes)

    def __contains__(self, class_path: str) -> bool:
        """Check if a node is registered."""
        return class_path in self._nodes
