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
    hparams:
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
from cuvis_ai_schemas.pipeline.ports import PortSpec

from .node_adapter import CuvisNodeAdapter, NodeRegistry
from .port_helpers import create_input_port, create_output_port


def _inferred_port_spec(is_input: bool) -> PortSpec:
    """Spec for a port known only from the pipeline's connections.

    Inferred inputs accept fan-in, so no edge of the yaml is dropped when two
    sources feed the same port.
    """
    return PortSpec(
        dtype="any",
        shape=(),
        description="(inferred from pipeline connections)",
        optional=is_input,
        variadic=is_input,
    )


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
        self.known_plugins: set[str] | None = None
        """Names of the registered plugins; when set, a pipeline's ``plugins:`` is checked."""
        self.loaded_plugins: list[str] = []
        """The ``plugins:`` block of the pipeline last loaded with :meth:`from_config`.

        A later :meth:`to_config` on the same (possibly edited) graph keeps any of
        these whose class the current registry can no longer attribute, so a
        plugin declared by the loaded pipeline is never dropped just because the
        registry's plugin set changed since the load (a folder switch, for one).
        """
        self.last_load_warnings: list[str] = []
        self.last_missing_connections: list[str] = []
        """YAML connections the last load could not draw, as ``source -> target``."""
        self._load_missing_nodes: set[str] = set()
        self._load_failed_nodes: list[str] = []
        self._load_failed_connections = 0
        self._load_inferred_port_classes: set[str] = set()
        self._placeholder_class_cache: dict[str, type] = {}

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
        self.last_missing_connections = []
        self._load_missing_nodes = set()
        self._load_failed_nodes = []
        self._load_failed_connections = 0
        self._load_inferred_port_classes = set()
        self._placeholder_class_cache = {}

        # Validate configuration with Pydantic. Do this before touching any
        # state that belongs to the graph still on screen: a config that
        # fails validation leaves that graph (and what it needs declared)
        # untouched, so the caller's existing pipeline is still intact.
        try:
            pipeline_config = PipelineConfig.from_dict(config)
        except Exception as e:
            logger.error(f"Pipeline configuration validation failed: {e}")
            raise ValueError(f"Invalid pipeline configuration: {e}") from e

        self.loaded_plugins = list(pipeline_config.plugins or [])

        # Note: Connection validation is done during graph construction
        # cuvis-ai-schemas PipelineConfig doesn't have validate_connections_reference_nodes()

        if self.known_plugins is not None:
            unknown = [p for p in pipeline_config.plugins or [] if p not in self.known_plugins]
            if unknown:
                self.last_load_warnings.append("Plugins not available: " + ", ".join(unknown))

        # Clear existing graph
        graph.clear_session()

        # Pre-scan connections for the port names each node is wired through.
        # A placeholder for an unknown class shares one synthesized class across
        # every instance of that class path (NodeGraphQt forbids a second
        # registration of the same type), so its ports must be the union over
        # all those instances. A known class whose manifest declares no ports
        # gets its own node's ports only, so two spec-less instances wired
        # through different connections don't leak ports into each other.
        name_to_class_path = {n.name: n.class_name for n in pipeline_config.nodes}
        input_port_hints_by_node: dict[str, set[str]] = {}
        output_port_hints_by_node: dict[str, set[str]] = {}
        input_port_hints_by_class: dict[str, set[str]] = {}
        output_port_hints_by_class: dict[str, set[str]] = {}
        for conn in pipeline_config.connections:
            src = self._parse_connection_string(conn.source)
            tgt = self._parse_connection_string(conn.target)
            if src and src[1] == "outputs":
                output_port_hints_by_node.setdefault(src[0], set()).add(src[2])
                cp = name_to_class_path.get(src[0])
                if cp:
                    output_port_hints_by_class.setdefault(cp, set()).add(src[2])
            if tgt and tgt[1] == "inputs":
                input_port_hints_by_node.setdefault(tgt[0], set()).add(tgt[2])
                cp = name_to_class_path.get(tgt[0])
                if cp:
                    input_port_hints_by_class.setdefault(cp, set()).add(tgt[2])

        # Create nodes
        node_map: dict[str, CuvisNodeAdapter] = {}

        for node_config in pipeline_config.nodes:
            node_dict = {
                "class_name": node_config.class_name,
                "name": node_config.name,
                "hparams": node_config.hparams,
            }
            known_class = self.node_registry.get_node_class(node_config.class_name) is not None
            if known_class:
                input_hints = input_port_hints_by_node.get(node_config.name)
                output_hints = output_port_hints_by_node.get(node_config.name)
            else:
                input_hints = input_port_hints_by_class.get(node_config.class_name)
                output_hints = output_port_hints_by_class.get(node_config.class_name)
            node = self._create_node(
                node_dict,
                graph,
                input_port_hints=input_hints,
                output_port_hints=output_hints,
            )
            if node:
                node_map[node.name()] = node

        # Create connections, then compare what the graph shows with the YAML:
        # a connect call can succeed and still drop an earlier edge (a second
        # source on a single-connection input replaces the first).
        for conn_config in pipeline_config.connections:
            self._create_connection([conn_config.source, conn_config.target], node_map, graph)
        self.last_missing_connections = self._missing_connections(
            pipeline_config.connections, node_map
        )
        self._load_failed_connections = len(self.last_missing_connections)

        # Auto-layout positions every loaded node, spaced by its own size.
        if node_map:
            self._auto_layout(graph)

        if self._load_missing_nodes:
            missing = ", ".join(sorted(self._load_missing_nodes))
            self.last_load_warnings.append(
                "Missing node classes (placeholders created): " + missing
            )
        if self._load_failed_nodes:
            failed = ", ".join(self._load_failed_nodes)
            self.last_load_warnings.append("Failed to create nodes: " + failed)
        if self.last_missing_connections:
            shown = self.last_missing_connections[:5]
            more = len(self.last_missing_connections) - len(shown)
            self.last_load_warnings.append(
                f"{len(self.last_missing_connections)} connection(s) could not be drawn: "
                + ", ".join(shown)
                + (f" and {more} more" if more else "")
            )
        if self._load_inferred_port_classes:
            names = sorted(c.rsplit(".", 1)[-1] for c in self._load_inferred_port_classes)
            self.last_load_warnings.append(
                "Ports taken from connections (the plugin manifest declares none): "
                + ", ".join(names)
            )

        logger.info(
            f"Loaded pipeline with {len(node_map)} nodes and "
            f"{len(pipeline_config.connections)} connections"
        )

        if pipeline_config.metadata is not None:
            return pipeline_config.metadata.model_dump()
        return {}

    def _create_node(
        self,
        node_config: dict[str, Any],
        graph: NodeGraph,
        input_port_hints: set[str] | None = None,
        output_port_hints: set[str] | None = None,
    ) -> CuvisNodeAdapter | None:
        """Create a NodeGraphQt node from configuration.

        Args:
            node_config: Node configuration dictionary
            graph: NodeGraphQt graph to add node to
            input_port_hints: Input port names referenced by connections,
                used to build placeholder ports when the class is unknown.
            output_port_hints: Output port names referenced by connections,
                used to build placeholder ports when the class is unknown.

        Returns:
            Created node or None if creation failed
        """
        class_path = node_config.get("class_name", "")
        node_name = node_config.get("name", "")
        hparams = node_config.get("hparams", {})
        execution_stages = node_config.get("execution_stages", ["always"])

        # Get the node class from registry. resolve_class_path tolerates a
        # class_path naming the defining module (cuvis-ai's own save format)
        # while the registry holds the plugin manifest's package export; the
        # registered path can then differ from the yaml's own string.
        resolved_class_path = self.node_registry.resolve_class_path(class_path)
        node_class = self.node_registry.get_node_class(class_path)
        known_class = node_class is not None

        if node_class is None:
            logger.warning(f"Unknown node class: {class_path}")
            if class_path:
                self._load_missing_nodes.add(class_path)
            # Create a placeholder with ports inferred from the yaml's
            # connection list so the graph topology survives the load.
            node_class = self._create_placeholder_class(
                class_path,
                input_ports=input_port_hints,
                output_ports=output_port_hints,
            )

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

            # A node resolved by last-segment fallback keeps the yaml's own
            # class_name, so a load-then-save round trip writes the pipeline
            # back unchanged instead of normalizing it to the registered path.
            if (
                known_class
                and resolved_class_path is not None
                and resolved_class_path != class_path
                and hasattr(node, "_cuvis_class_path")
            ):
                node._cuvis_class_path = class_path

            # Set cuvis-specific attributes
            if hasattr(node, "cuvis_hparams"):
                node.cuvis_hparams = hparams
            if hasattr(node, "cuvis_execution_stages"):
                node.cuvis_execution_stages = set(execution_stages)

            if known_class and self._add_inferred_ports(node, input_port_hints, output_port_hints):
                self._load_inferred_port_classes.add(class_path)

            return node  # type: ignore

        except Exception as e:
            logger.error(f"Failed to create node {class_path}: {e}")
            label = node_name or class_path or "Unknown"
            self._load_failed_nodes.append(label)
            return None

    @staticmethod
    def _add_inferred_ports(
        node: CuvisNodeAdapter,
        input_ports: set[str] | None,
        output_ports: set[str] | None,
    ) -> bool:
        """Add the ports connections name but the node's class does not declare.

        A plugin manifest may list a class without port specs; its node would
        otherwise come up portless and lose every connection.

        Returns:
            True if any port was added.
        """
        added = False
        for name in sorted(set(input_ports or ()) - set(node.inputs())):
            spec = _inferred_port_spec(is_input=True)
            node._cuvis_input_specs[name] = spec
            create_input_port(node, name, spec)
            added = True
        for name in sorted(set(output_ports or ()) - set(node.outputs())):
            spec = _inferred_port_spec(is_input=False)
            node._cuvis_output_specs[name] = spec
            create_output_port(node, name, spec)
            added = True
        if added:
            node.view.draw_node()
        return added

    def _missing_connections(
        self,
        connections: list[ConnectionConfig],
        node_map: dict[str, CuvisNodeAdapter],
    ) -> list[str]:
        """Return the YAML connections the graph does not show, as ``source -> target``."""
        drawn = {
            (node.name(), port.name(), other.node().name(), other.name())
            for node in node_map.values()
            for port in node.output_ports()
            for other in port.connected_ports()
        }
        missing = []
        for conn in connections:
            src = self._parse_connection_string(conn.source)
            tgt = self._parse_connection_string(conn.target)
            if not src or not tgt or (src[0], src[2], tgt[0], tgt[2]) not in drawn:
                missing.append(f"{conn.source} -> {conn.target}")
        return missing

    def _create_placeholder_class(
        self,
        class_path: str,
        input_ports: set[str] | None = None,
        output_ports: set[str] | None = None,
    ) -> type:
        """Create a placeholder node class for unknown node types.

        Ports are inferred from connection references in the loaded yaml, so
        a pipeline that uses a missing plugin still preserves its topology.
        Each class_path maps to a single cached placeholder class — repeated
        instances of the same unknown class share one class with the union
        of port hints, satisfying NodeGraphQt's no-duplicate-type rule.

        Args:
            class_path: Full class path of the unknown node
            input_ports: Input port names referenced by connections
            output_ports: Output port names referenced by connections

        Returns:
            Placeholder node class
        """
        cached = self._placeholder_class_cache.get(class_path)
        if cached is not None:
            return cached

        class_name = class_path.split(".")[-1] if "." in class_path else class_path
        identifier = class_path.replace(".", "_")
        in_ports = frozenset(input_ports or ())
        out_ports = frozenset(output_ports or ())

        class PlaceholderNode(CuvisNodeAdapter):
            __identifier__ = f"cuvis_ai.placeholder.{identifier}"
            NODE_NAME = f"{class_name} (Unknown)"

            def __init__(self) -> None:
                super().__init__()
                self._cuvis_class_path = class_path
                self._cuvis_class_name = class_name
                self.set_name(class_name)
                self.set_color(200, 50, 50)  # Red for unknown
                for name in sorted(in_ports):
                    spec = _inferred_port_spec(is_input=True)
                    self._cuvis_input_specs[name] = spec
                    create_input_port(self, name, spec)
                for name in sorted(out_ports):
                    spec = _inferred_port_spec(is_input=False)
                    self._cuvis_output_specs[name] = spec
                    create_output_port(self, name, spec)

        self._placeholder_class_cache[class_path] = PlaceholderNode
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

    @staticmethod
    def _node_size(node: CuvisNodeAdapter) -> tuple[int, int]:
        """Return (width, height) from the node's view, or a 250x100 fallback.

        A placeholder or freshly created node's view can still report
        non-numeric or zero sizes before its first paint, so anything that
        isn't a plain number falls back to the default footprint.
        """
        view = getattr(node, "view", None)
        width = getattr(view, "width", None)
        height = getattr(view, "height", None)
        if (
            isinstance(width, (int, float))
            and isinstance(height, (int, float))
            and width
            and height
        ):
            return int(width), int(height)
        return 250, 100

    def _auto_layout(self, graph: NodeGraph) -> None:
        """Apply automatic layout to nodes in the graph.

        Uses a left-to-right flow layout based on connections, spacing each
        node by its own view size so nodes with long port names don't
        overlap their neighbours.

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

        # Position nodes: each column starts where the previous column's
        # widest node ends, plus a gap; within a column each node starts
        # where the previous node's bottom ends, plus a gap.
        column_gap = 80
        row_gap = 40
        node_dict = {n.name(): n for n in nodes}

        x = 0
        for column in columns:
            y = 0
            widest = 0
            for node_name in column:
                node = node_dict.get(node_name)
                if not node:
                    continue
                width, height = self._node_size(node)
                node.set_pos(x, y)
                y += height + row_gap
                widest = max(widest, width)
            x += widest + column_gap

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

    def _collect_pipeline_plugins(
        self, graph_nodes: list[Any], nodes_list: list[NodeConfig]
    ) -> list[str] | None:
        """Derive the bare plugin-name set the pipeline depends on.

        A node's own stored owner (``cuvis_plugin_name``, set when the node was
        created) wins first: the registry can resolve a node's class_name to a
        different plugin's class of the same bare name after a folder switch
        (the shared registry is cleared and re-registered while the graph
        itself is kept), and the node's stored owner is the one that is
        actually still on screen. Only when the node carries no stored owner
        does the current registry's ``plugin_name`` for its class_name apply.
        A core built-in is known to the registry (or was created) with an
        empty ``plugin_name`` and needs no declaration. A node with neither a
        stored owner nor a registry entry (a placeholder for a class unknown
        even at load time) can't be attributed; it's recorded as a load
        warning, and the plugins the pipeline declared when it was loaded
        (:attr:`loaded_plugins`) are kept instead so nothing declared is
        silently lost.

        Args:
            graph_nodes: The live graph nodes, in the same order as nodes_list.
            nodes_list: Validated node configs from the graph.

        Returns:
            Sorted unique plugin names, or ``None`` when no plugin nodes are
            present and nothing was declared at load (so the field is omitted
            from the emitted yaml).
        """
        plugin_names: set[str] = set()
        unknown: list[str] = []
        for node, node_cfg in zip(graph_nodes, nodes_list):
            owner = getattr(node, "cuvis_plugin_name", "")
            plugin_name = owner if isinstance(owner, str) else ""
            if not plugin_name:
                info = self.node_registry.get_node_info(node_cfg.class_name)
                if info is not None:
                    plugin_name = info.get("plugin_name") or ""
                else:
                    unknown.append(node_cfg.class_name)
            if plugin_name:
                plugin_names.add(plugin_name)
        if unknown:
            plugin_names.update(self.loaded_plugins)
            self.last_load_warnings.append(
                "Could not determine the owning plugin for: "
                + ", ".join(sorted(set(unknown)))
                + ". Add these to the pipeline's 'plugins:' block manually if needed."
            )
        return sorted(plugin_names) or None

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

        # Derive the plugin set the pipeline depends on. The refactored loader
        # requires a bare-name `plugins:` block and resolves each node's
        # class_name against it. A node's owning plugin comes from the registry
        # (populated by ListAvailableNodes): cuvis-ai node-lib classes resolve to
        # "cuvis_ai_builtin", core built-ins carry an empty plugin_name and need
        # no declaration. Unknown/placeholder classes can't be attributed.
        plugins_list = self._collect_pipeline_plugins(graph.all_nodes(), nodes_list)

        # Create validated PipelineConfig
        try:
            pipeline_config = PipelineConfig(
                metadata=metadata if metadata else None,
                plugins=plugins_list,
                nodes=nodes_list,
                connections=connections_list,
            )

            # Note: cuvis-ai-schemas PipelineConfig doesn't have validate_connections_reference_nodes()
            # Connection validation happens during from_config when creating the graph

            # Return validated configuration as dict. Drop a null plugins field so
            # the emitted yaml stays clean when the graph has no plugin nodes.
            result = pipeline_config.to_dict()
            if result.get("plugins") is None:
                result.pop("plugins", None)
            return result

        except Exception as e:
            logger.error(f"Failed to create validated pipeline config: {e}")
            # Fallback to basic dict structure
            return {
                "metadata": metadata or {"name": "Untitled Pipeline"},
                **({"plugins": plugins_list} if plugins_list else {}),
                "nodes": [
                    {
                        "class_name": n.class_name,
                        "name": n.name,
                        "hparams": n.hparams,
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
