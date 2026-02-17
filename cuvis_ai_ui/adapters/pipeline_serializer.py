"""Pipeline serialization between cuvis-ai YAML and NodeGraphQt graph.

This module provides bidirectional conversion:
- YAML (cuvis-ai pipeline format) -> NodeGraphQt graph
- NodeGraphQt graph -> YAML (cuvis-ai pipeline format)

The YAML format follows cuvis-ai-core conventions with Pydantic validation:
```yaml
metadata:
  name: "Pipeline Name"
  description: "Optional description"
  tags: [tag1, tag2]

nodes:
  - class_name: cuvis_ai.node.normalization.MinMaxNormalizer
    name: normalizer
    params:
      min: 0.0
      max: 1.0

connections:
  - source: source_node.outputs.output
    target: target_node.inputs.input
```
"""

import re
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from NodeGraphQt import NodeGraph

from cuvis_ai_schemas.pipeline import PipelineConfig, ConnectionConfig, NodeConfig

from .node_adapter import CuvisNodeAdapter, NodeRegistry


class PipelineSerializer:
    """Bidirectional serializer between cuvis-ai YAML and NodeGraphQt.

    Handles loading pipelines from YAML files, converting them to
    NodeGraphQt graphs for visual editing, and saving back to YAML.

    Attributes:
        node_registry: Registry of available node types
    """

    def __init__(self, node_registry: NodeRegistry) -> None:
        """Initialize the serializer.

        Args:
            node_registry: Registry of available cuvis-ai nodes
        """
        self.node_registry = node_registry
        self.last_load_warnings: list[str] = []
        self._load_missing_nodes: set[str] = set()
        self._load_failed_nodes: list[str] = []
        self._load_failed_connections = 0

    def from_yaml_file(self, path: str | Path, graph: NodeGraph) -> dict[str, Any]:
        """Load a pipeline from a YAML file into a NodeGraphQt graph.

        Args:
            path: Path to the YAML file
            graph: NodeGraphQt graph to populate

        Returns:
            Pipeline metadata dictionary

        Raises:
            FileNotFoundError: If the YAML file doesn't exist
            ValueError: If the YAML format is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Pipeline file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return self.from_config(config, graph)

    def from_yaml_string(self, yaml_str: str, graph: NodeGraph) -> dict[str, Any]:
        """Load a pipeline from a YAML string into a NodeGraphQt graph.

        Args:
            yaml_str: YAML configuration string
            graph: NodeGraphQt graph to populate

        Returns:
            Pipeline metadata dictionary
        """
        config = yaml.safe_load(yaml_str)
        return self.from_config(config, graph)

    def from_config(self, config: dict[str, Any], graph: NodeGraph) -> dict[str, Any]:
        """Load a pipeline configuration into a NodeGraphQt graph.

        Args:
            config: Pipeline configuration dictionary
            graph: NodeGraphQt graph to populate

        Returns:
            Pipeline metadata dictionary

        Raises:
            ValueError: If the configuration is invalid
        """
        # Reset load warnings
        self.last_load_warnings = []
        self._load_missing_nodes = set()
        self._load_failed_nodes = []
        self._load_failed_connections = 0

        # Validate configuration with Pydantic
        try:
            pipeline_config = PipelineConfig.from_dict(config)
        except Exception as e:
            logger.error(f"Pipeline configuration validation failed: {e}")
            raise ValueError(f"Invalid pipeline configuration: {e}") from e

        # Note: Connection validation is done during graph construction
        # cuvis-ai-schemas PipelineConfig doesn't have validate_connections_reference_nodes()

        # Clear existing graph
        graph.clear_session()

        # Create nodes
        node_map: dict[str, CuvisNodeAdapter] = {}

        for i, node_config in enumerate(pipeline_config.nodes):
            node_dict = {
                "class_name": node_config.class_name,
                "name": node_config.name,
                "hparams": node_config.params,
            }
            node = self._create_node(node_dict, graph)
            if node:
                node_map[node.name()] = node
                # Position nodes in a grid layout initially
                row = i // 4
                col = i % 4
                node.set_pos(col * 250, row * 150)

        # Create connections
        for conn_config in pipeline_config.connections:
            connection = [conn_config.source, conn_config.target]
            if not self._create_connection(connection, node_map, graph):
                self._load_failed_connections += 1

        # Auto-layout if more than a few nodes
        if len(node_map) > 2:
            self._auto_layout(graph)

        if self._load_missing_nodes:
            missing = ", ".join(sorted(self._load_missing_nodes))
            self.last_load_warnings.append(
                "Missing node classes (placeholders created): " + missing
            )
        if self._load_failed_nodes:
            failed = ", ".join(self._load_failed_nodes)
            self.last_load_warnings.append("Failed to create nodes: " + failed)
        if self._load_failed_connections:
            self.last_load_warnings.append(
                f"{self._load_failed_connections} connection(s) could not be created."
            )

        logger.info(
            f"Loaded pipeline with {len(node_map)} nodes and "
            f"{len(pipeline_config.connections)} connections"
        )

        if pipeline_config.metadata is not None:
            return pipeline_config.metadata.model_dump()
        return {}

    def _create_node(
        self, node_config: dict[str, Any], graph: NodeGraph
    ) -> CuvisNodeAdapter | None:
        """Create a NodeGraphQt node from configuration.

        Args:
            node_config: Node configuration dictionary
            graph: NodeGraphQt graph to add node to

        Returns:
            Created node or None if creation failed
        """
        class_path = node_config.get("class_name", "")
        node_name = node_config.get("name", "")
        hparams = node_config.get("hparams", {})
        execution_stages = node_config.get("execution_stages", ["always"])

        # Get the node class from registry
        node_class = self.node_registry.get_node_class(class_path)

        if node_class is None:
            logger.warning(f"Unknown node class: {class_path}")
            if class_path:
                self._load_missing_nodes.add(class_path)
            # Create a placeholder node
            node_class = self._create_placeholder_class(class_path)

        node_type = getattr(node_class, "type_", None)
        if node_type is None:
            node_type = f"{node_class.__identifier__}.{node_class.__name__}"

        # Ensure the node type is registered with the graph
        try:
            if node_type not in graph.registered_nodes():
                graph.register_node(node_class)
        except Exception as e:
            # Registration can fail if already registered or graph rejects duplicates
            logger.debug(f"Node registration skipped for {node_type}: {e}")

        # Create the node
        try:
            node = graph.create_node(node_type)
            node.set_name(node_name)

            # Set cuvis-specific attributes
            if hasattr(node, "cuvis_hparams"):
                node.cuvis_hparams = hparams
            if hasattr(node, "cuvis_execution_stages"):
                node.cuvis_execution_stages = set(execution_stages)

            return node  # type: ignore

        except Exception as e:
            logger.error(f"Failed to create node {class_path}: {e}")
            label = node_name or class_path or "Unknown"
            self._load_failed_nodes.append(label)
            return None

    def _create_placeholder_class(self, class_path: str) -> type:
        """Create a placeholder node class for unknown node types.

        Args:
            class_path: Full class path of the unknown node

        Returns:
            Placeholder node class
        """
        class_name = class_path.split(".")[-1] if "." in class_path else class_path
        identifier = class_path.replace(".", "_")

        class PlaceholderNode(CuvisNodeAdapter):
            __identifier__ = f"cuvis_ai.placeholder.{identifier}"
            NODE_NAME = f"{class_name} (Unknown)"

            def __init__(self) -> None:
                super().__init__()
                self._cuvis_class_path = class_path
                self._cuvis_class_name = class_name
                self.set_name(class_name)
                self.set_color(200, 50, 50)  # Red for unknown

        return PlaceholderNode

    def _create_connection(
        self,
        connection: list[str],
        node_map: dict[str, CuvisNodeAdapter],
        graph: NodeGraph,
    ) -> bool:
        """Create a connection between two nodes.

        Connection format: ["source_node.outputs.port", "target_node.inputs.port"]

        Args:
            connection: Connection specification [source, target]
            node_map: Mapping of node names to nodes
            graph: NodeGraphQt graph

        Returns:
            True if connection was created successfully
        """
        if len(connection) != 2:
            logger.warning(f"Invalid connection format: {connection}")
            return False

        source_str, target_str = connection

        # Parse connection strings
        source_parts = self._parse_connection_string(source_str)
        target_parts = self._parse_connection_string(target_str)

        if not source_parts or not target_parts:
            logger.warning(f"Failed to parse connection: {connection}")
            return False

        source_node_name, source_type, source_port = source_parts
        target_node_name, target_type, target_port = target_parts

        # Validate types
        if source_type != "outputs" or target_type != "inputs":
            logger.warning(f"Invalid connection types: {source_type} -> {target_type}")
            return False

        # Get nodes
        source_node = node_map.get(source_node_name)
        target_node = node_map.get(target_node_name)

        if not source_node:
            logger.warning(f"Source node not found: {source_node_name}")
            return False
        if not target_node:
            logger.warning(f"Target node not found: {target_node_name}")
            return False

        # Get ports
        source_output = source_node.get_output(source_port)
        target_input = target_node.get_input(target_port)

        if not source_output:
            logger.warning(f"Source port not found: {source_node_name}.{source_port}")
            return False
        if not target_input:
            logger.warning(f"Target port not found: {target_node_name}.{target_port}")
            return False

        # Create connection
        try:
            source_output.connect_to(target_input)
            return True
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            return False

    def _parse_connection_string(self, conn_str: str) -> tuple[str, str, str] | None:
        """Parse a connection string into (node_name, type, port_name).

        Format: "node_name.outputs.port_name" or "node_name.inputs.port_name"

        Args:
            conn_str: Connection string to parse

        Returns:
            Tuple of (node_name, type, port_name) or None if invalid
        """
        # Pattern: node_name.outputs.port_name or node_name.inputs.port_name
        pattern = r"^(.+)\.(outputs|inputs)\.(.+)$"
        match = re.match(pattern, conn_str)

        if match:
            return match.group(1), match.group(2), match.group(3)

        return None

    def _auto_layout(self, graph: NodeGraph) -> None:
        """Apply automatic layout to nodes in the graph.

        Uses a simple left-to-right flow layout based on connections.

        Args:
            graph: NodeGraphQt graph to layout
        """
        nodes = graph.all_nodes()
        if not nodes:
            return

        # Build dependency graph
        dependencies: dict[str, set[str]] = {n.name(): set() for n in nodes}
        for node in nodes:
            for input_port in node.input_ports():
                for connected_port in input_port.connected_ports():
                    source_node = connected_port.node()
                    dependencies[node.name()].add(source_node.name())

        # Topological sort to determine column order
        columns: list[list[str]] = []
        placed: set[str] = set()

        while len(placed) < len(nodes):
            # Find nodes with all dependencies satisfied
            ready = [
                name
                for name, deps in dependencies.items()
                if name not in placed and deps.issubset(placed)
            ]

            if not ready:
                # Cycle detected, place remaining nodes
                ready = [name for name in dependencies if name not in placed]

            columns.append(ready)
            placed.update(ready)

        # Position nodes
        x_spacing = 300
        y_spacing = 150
        node_dict = {n.name(): n for n in nodes}

        for col_idx, column in enumerate(columns):
            for row_idx, node_name in enumerate(column):
                node = node_dict.get(node_name)
                if node:
                    x = col_idx * x_spacing
                    y = row_idx * y_spacing
                    node.set_pos(x, y)

    def to_yaml_file(
        self,
        graph: NodeGraph,
        path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save a NodeGraphQt graph to a YAML file.

        Args:
            graph: NodeGraphQt graph to save
            path: Output file path
            metadata: Optional metadata to include
        """
        config = self.to_config(graph, metadata)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved pipeline to {path}")

    def to_yaml_string(
        self,
        graph: NodeGraph,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Convert a NodeGraphQt graph to a YAML string.

        Args:
            graph: NodeGraphQt graph to convert
            metadata: Optional metadata to include

        Returns:
            YAML configuration string
        """
        config = self.to_config(graph, metadata)
        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def to_config(
        self,
        graph: NodeGraph,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert a NodeGraphQt graph to a configuration dictionary.

        Args:
            graph: NodeGraphQt graph to convert
            metadata: Optional metadata to include

        Returns:
            Pipeline configuration dictionary with Pydantic validation
        """
        # Build node configs
        nodes_list = []
        for node in graph.all_nodes():
            if hasattr(node, "get_cuvis_config"):
                node_dict = node.get_cuvis_config()
            else:
                # Fallback for non-cuvis nodes
                node_dict = {
                    "class_name": getattr(node, "_cuvis_class_path", node.__class__.__name__),
                    "name": node.name(),
                }

            # Convert internal 'hparams' to schema 'params'
            if "hparams" in node_dict and "params" not in node_dict:
                node_dict["params"] = node_dict.pop("hparams")

            nodes_list.append(NodeConfig(**node_dict))

        # Build connection configs using source/target format
        connections_list = []
        for node in graph.all_nodes():
            for output_port in node.output_ports():
                for connected_port in output_port.connected_ports():
                    target_node = connected_port.node()
                    conn = ConnectionConfig(
                        source=f"{node.name()}.outputs.{output_port.name()}",
                        target=f"{target_node.name()}.inputs.{connected_port.name()}",
                    )
                    connections_list.append(conn)

        # Create validated PipelineConfig
        try:
            pipeline_config = PipelineConfig(
                metadata=metadata if metadata else None,
                nodes=nodes_list,
                connections=connections_list,
            )

            # Note: cuvis-ai-schemas PipelineConfig doesn't have validate_connections_reference_nodes()
            # Connection validation happens during from_config when creating the graph

            # Return validated configuration as dict
            return pipeline_config.to_dict()

        except Exception as e:
            logger.error(f"Failed to create validated pipeline config: {e}")
            # Fallback to basic dict structure
            return {
                "metadata": metadata or {"name": "Untitled Pipeline"},
                "nodes": [
                    {
                        "class_name": n.class_name,
                        "name": n.name,
                        "params": n.params,
                    }
                    for n in nodes_list
                ],
                "connections": [
                    {
                        "source": c.source,
                        "target": c.target,
                    }
                    for c in connections_list
                ],
            }

    def validate_round_trip(
        self, original_config: dict[str, Any], graph: NodeGraph
    ) -> tuple[bool, list[str]]:
        """Validate that a graph can be serialized and deserialized correctly.

        Args:
            original_config: Original configuration
            graph: Graph loaded from original config

        Returns:
            Tuple of (is_valid, list of differences)
        """
        differences: list[str] = []

        # Re-serialize the graph
        new_config = self.to_config(graph, original_config.get("metadata"))

        # Compare nodes
        orig_nodes = {n["name"]: n for n in original_config.get("nodes", [])}
        new_nodes = {n["name"]: n for n in new_config.get("nodes", [])}

        for name in orig_nodes:
            if name not in new_nodes:
                differences.append(f"Missing node: {name}")
            elif orig_nodes[name].get("class_name") != new_nodes[name].get("class_name"):
                differences.append(
                    f"Node class mismatch for {name}: "
                    f"{orig_nodes[name].get('class_name')} vs {new_nodes[name].get('class_name')}"
                )

        for name in new_nodes:
            if name not in orig_nodes:
                differences.append(f"Extra node: {name}")

        # Compare connections
        orig_conns = set(tuple(c) for c in original_config.get("connections", []))
        new_conns = set(tuple(c) for c in new_config.get("connections", []))

        for conn in orig_conns - new_conns:
            differences.append(f"Missing connection: {conn}")

        for conn in new_conns - orig_conns:
            differences.append(f"Extra connection: {conn}")

        return len(differences) == 0, differences
