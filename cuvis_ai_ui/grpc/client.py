"""gRPC client wrapper for cuvis-ai-core service.

This is a CLIENT-ONLY implementation - no gRPC service implementation.
All business logic resides in cuvis-ai-core server.
"""

import time
from pathlib import Path
from typing import Any

import grpc
from loguru import logger

from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2, cuvis_ai_pb2_grpc


def _dtype_to_string(dtype_enum: int) -> str:
    """Convert proto DType enum to string representation.

    Parameters
    ----------
    dtype_enum : int
        Proto DType enum value

    Returns
    -------
    str
        String representation (e.g., "float32", "int32")
    """
    dtype_map = {
        cuvis_ai_pb2.D_TYPE_FLOAT32: "float32",
        cuvis_ai_pb2.D_TYPE_FLOAT64: "float64",
        cuvis_ai_pb2.D_TYPE_INT32: "int32",
        cuvis_ai_pb2.D_TYPE_INT64: "int64",
        cuvis_ai_pb2.D_TYPE_UINT8: "uint8",
        cuvis_ai_pb2.D_TYPE_BOOL: "bool",
        cuvis_ai_pb2.D_TYPE_FLOAT16: "float16",
        cuvis_ai_pb2.D_TYPE_UINT16: "uint16",
    }
    return dtype_map.get(dtype_enum, "unknown")


def _convert_port_specs(port_specs_map: dict) -> list[dict[str, Any]]:
    """Convert proto port specs map to list of port spec dicts.

    Parameters
    ----------
    port_specs_map : dict
        Map from port name to PortSpecList proto message

    Returns
    -------
    list[dict[str, Any]]
        List of port spec dicts with keys: name, dtype, shape, optional, description
    """
    result = []
    for port_name, port_spec_list in port_specs_map.items():
        for spec in port_spec_list.specs:
            # Convert shape from list to string format
            # E.g., [-1, -1, -1, -1] -> "[-1, -1, -1, -1]"
            shape_list = list(spec.shape) if spec.shape else []
            shape_str = str(shape_list) if shape_list else "any"

            result.append(
                {
                    "name": spec.name if spec.name else port_name,
                    "dtype": _dtype_to_string(spec.dtype),
                    "shape": shape_str,
                    "optional": spec.optional,
                    "description": spec.description if spec.description else "",
                }
            )
    return result


class CuvisAIClient:
    """gRPC client wrapper for cuvis-ai-core service.

    Provides high-level Python interface to cuvis-ai-core gRPC API with:
    - Automatic connection management with retry logic
    - Session lifecycle handling
    - User-friendly error messages
    - Context manager support

    Examples
    --------
    >>> with CuvisAIClient() as client:
    ...     nodes = client.list_available_nodes()
    ...     print(f"Found {len(nodes)} nodes")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50051,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """Initialize cuvis-ai gRPC client.

        Parameters
        ----------
        host : str, default="localhost"
            gRPC server host
        port : int, default=50051
            gRPC server port
        timeout : int, default=30
            RPC timeout in seconds
        max_retries : int, default=3
            Maximum connection retry attempts
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries

        self.channel: grpc.Channel | None = None
        self.stub: cuvis_ai_pb2_grpc.CuvisAIServiceStub | None = None
        self.session_id: str | None = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to gRPC server with retry logic.

        Returns
        -------
        bool
            True if connection successful, False otherwise

        Raises
        ------
        ConnectionError
            If connection fails after all retries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    f"Connecting to cuvis-ai-core at {self.host}:{self.port} "
                    f"(attempt {attempt}/{self.max_retries})"
                )

                # Create channel with max message size (100MB for large pipelines)
                options = [
                    ("grpc.max_receive_message_length", 100 * 1024 * 1024),
                    ("grpc.max_send_message_length", 100 * 1024 * 1024),
                ]
                self.channel = grpc.insecure_channel(f"{self.host}:{self.port}", options=options)
                self.stub = cuvis_ai_pb2_grpc.CuvisAIServiceStub(self.channel)

                # Health check: try to create session
                response = self.stub.CreateSession(
                    cuvis_ai_pb2.CreateSessionRequest(),
                    timeout=self.timeout,
                )
                self.session_id = response.session_id
                self._connected = True

                logger.info(
                    f"Connected to cuvis-ai-core at {self.host}:{self.port}, "
                    f"session_id={self.session_id}"
                )
                return True

            except grpc.RpcError as e:
                logger.warning(
                    f"Connection attempt {attempt}/{self.max_retries} failed: {e.code()}"
                )

                if attempt < self.max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** (attempt - 1)
                    logger.debug(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    error_msg = (
                        f"Failed to connect to cuvis-ai-core at {self.host}:{self.port} "
                        f"after {self.max_retries} attempts.\n\n"
                        f"Please ensure the server is running:\n"
                        f"  cd D:/code-repos/cuvis-ai-core\n"
                        f"  uv run python -m cuvis_ai_core.grpc.production_server\n\n"
                        f"Error: {e.details()}"
                    )
                    logger.error(error_msg)
                    raise ConnectionError(error_msg) from e

        return False

    def disconnect(self) -> bool:
        """Disconnect from gRPC server and close session.

        Returns
        -------
        bool
            True if disconnection successful
        """
        if not self._connected:
            logger.debug("Already disconnected")
            return True

        try:
            # Close session if exists
            if self.session_id and self.stub:
                self.close_session()

            # Close channel
            if self.channel:
                self.channel.close()

            self._connected = False
            logger.info("Disconnected from cuvis-ai-core")
            return True

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            return False

    # Session Management
    # ------------------

    def create_session(self) -> str:
        """Create a new session (usually called automatically on connect).

        Returns
        -------
        str
            Session ID

        Raises
        ------
        RuntimeError
            If not connected or session creation fails
        """
        if not self._connected or not self.stub:
            raise RuntimeError("Not connected to server")

        try:
            response = self.stub.CreateSession(
                cuvis_ai_pb2.CreateSessionRequest(),
                timeout=self.timeout,
            )
            self.session_id = response.session_id
            logger.debug(f"Created session: {self.session_id}")
            return self.session_id

        except grpc.RpcError as e:
            logger.error(f"Failed to create session: {e.details()}")
            raise RuntimeError(f"Failed to create session: {e.details()}") from e

    def close_session(self) -> bool:
        """Close current session.

        Returns
        -------
        bool
            True if successful
        """
        if not self.session_id or not self.stub:
            return True

        try:
            response = self.stub.CloseSession(
                cuvis_ai_pb2.CloseSessionRequest(session_id=self.session_id),
                timeout=self.timeout,
            )
            logger.debug(f"Closed session: {self.session_id}")
            self.session_id = None
            return response.success

        except grpc.RpcError as e:
            logger.warning(f"Failed to close session: {e.details()}")
            return False

    # Plugin Management
    # -----------------

    def load_plugins(self, manifest_path: str | Path) -> dict[str, Any]:
        """Load plugins from manifest file.

        Parameters
        ----------
        manifest_path : str | Path
            Path to plugins.yaml or plugins.json manifest file

        Returns
        -------
        dict[str, Any]
            Response with:
            - success (bool): Overall success status
            - loaded_plugins (list[str]): Successfully loaded plugin names
            - failed_plugins (list[str]): Failed plugin names

        Raises
        ------
        RuntimeError
            If not connected or load fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            import json
            from pathlib import Path

            import yaml

            # Read manifest file
            manifest_path = Path(manifest_path)
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

            with open(manifest_path, "r") as f:
                # Parse YAML (also handles JSON)
                manifest_dict = yaml.safe_load(f)

            # Convert to JSON for gRPC transport
            manifest_json = json.dumps(manifest_dict)

            # Send to server
            response = self.stub.LoadPlugins(
                cuvis_ai_pb2.LoadPluginsRequest(
                    session_id=self.session_id,
                    manifest=cuvis_ai_pb2.PluginManifest(config_bytes=manifest_json.encode()),
                ),
                timeout=self.timeout,
            )

            logger.info(
                f"Loaded {len(response.loaded_plugins)} plugins: "
                f"{', '.join(response.loaded_plugins)}"
            )

            if response.failed_plugins:
                logger.warning(
                    f"Failed to load {len(response.failed_plugins)} plugins: "
                    f"{', '.join(response.failed_plugins)}"
                )

            loaded = list(response.loaded_plugins)
            failed = list(response.failed_plugins.keys())
            return {
                "success": len(loaded) > 0 and len(failed) == 0,
                "loaded_plugins": loaded,
                "failed_plugins": failed,
            }

        except grpc.RpcError as e:
            logger.error(f"Failed to load plugins: {e.details()}")
            raise RuntimeError(f"Failed to load plugins: {e.details()}") from e

    # Node Discovery
    # --------------

    def list_available_nodes(self) -> list[dict[str, Any]]:
        """List all available nodes (builtin + catalog + plugins).

        Returns
        -------
        list[dict[str, Any]]
            List of node info dicts with keys:
            - class_name (str): Short class name
            - full_path (str): Full import path
            - source (str): "builtin" | "catalog" | "plugin"
            - plugin_name (str, optional): If from plugin
            - input_specs (list[dict]): Input port specifications
            - output_specs (list[dict]): Output port specifications

        Raises
        ------
        RuntimeError
            If not connected or RPC fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            response = self.stub.ListAvailableNodes(
                cuvis_ai_pb2.ListAvailableNodesRequest(session_id=self.session_id),
                timeout=self.timeout,
            )

            nodes = []
            for node_info in response.nodes:
                # Convert proto port specs to dict format
                input_specs = _convert_port_specs(node_info.input_specs)
                output_specs = _convert_port_specs(node_info.output_specs)

                nodes.append(
                    {
                        "class_name": node_info.class_name,
                        "full_path": node_info.full_path,
                        "source": node_info.source,
                        "plugin_name": node_info.plugin_name if node_info.plugin_name else None,
                        "input_specs": input_specs,
                        "output_specs": output_specs,
                    }
                )

            logger.debug(f"Listed {len(nodes)} available nodes")
            return nodes

        except grpc.RpcError as e:
            logger.error(f"Failed to list nodes: {e.details()}")
            raise RuntimeError(f"Failed to list nodes: {e.details()}") from e

    # Config Resolution (Hydra Integration)
    # --------------------------------------

    def resolve_config(
        self,
        config_type: str,
        path: str,
        overrides: list[str] | None = None,
    ) -> dict[str, Any]:
        """Resolve Hydra config with overrides.

        Parameters
        ----------
        config_type : str
            Config type: "pipeline" | "trainrun" | "data" | "training"
        path : str
            Relative or absolute path to config file
        overrides : list[str], optional
            Hydra overrides like ["optimizer.lr=0.001", "batch_size=32"]

        Returns
        -------
        dict[str, Any]
            Fully resolved config

        Raises
        ------
        RuntimeError
            If not connected or resolution fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            response = self.stub.ResolveConfig(
                cuvis_ai_pb2.ResolveConfigRequest(
                    session_id=self.session_id,
                    config_type=config_type,
                    path=path,
                    overrides=overrides or [],
                ),
                timeout=self.timeout,
            )

            # Parse JSON bytes to dict
            import json

            config = json.loads(response.config_bytes)
            logger.debug(f"Resolved {config_type} config from {path}")
            return config

        except grpc.RpcError as e:
            logger.error(f"Failed to resolve config: {e.details()}")
            raise RuntimeError(f"Failed to resolve config: {e.details()}") from e

    # Pipeline Operations
    # -------------------

    def load_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        """Load pipeline from config dict.

        Parameters
        ----------
        config : dict[str, Any]
            Pipeline config with keys: metadata, nodes, connections

        Returns
        -------
        dict[str, Any]
            Response with success status and metadata

        Raises
        ------
        RuntimeError
            If not connected or load fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            import json

            config_json = json.dumps(config)

            response = self.stub.LoadPipeline(
                cuvis_ai_pb2.LoadPipelineRequest(
                    session_id=self.session_id,
                    pipeline=cuvis_ai_pb2.PipelineConfig(config_bytes=config_json.encode()),
                ),
                timeout=self.timeout,
            )

            logger.info(f"Loaded pipeline: {config.get('metadata', {}).get('name', 'Unnamed')}")
            return {
                "success": response.success,
                "metadata": {
                    "name": response.metadata.name,
                    "description": response.metadata.description,
                    "tags": list(response.metadata.tags),
                },
            }

        except grpc.RpcError as e:
            logger.error(f"Failed to load pipeline: {e.details()}")
            raise RuntimeError(f"Failed to load pipeline: {e.details()}") from e

    def save_pipeline(
        self,
        pipeline_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save current pipeline to YAML file.

        Parameters
        ----------
        pipeline_path : str | Path
            Path where to save pipeline YAML
        metadata : dict[str, Any], optional
            Pipeline metadata (name, description, tags)

        Returns
        -------
        dict[str, Any]
            Response with paths to saved files

        Raises
        ------
        RuntimeError
            If not connected or save fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            pipeline_path = str(pipeline_path)

            # Build metadata message
            metadata_msg = None
            if metadata:
                metadata_msg = cuvis_ai_pb2.PipelineMetadata(
                    name=metadata.get("name", ""),
                    description=metadata.get("description", ""),
                    tags=metadata.get("tags", []),
                    author=metadata.get("author", ""),
                )

            response = self.stub.SavePipeline(
                cuvis_ai_pb2.SavePipelineRequest(
                    session_id=self.session_id,
                    pipeline_path=pipeline_path,
                    metadata=metadata_msg,
                ),
                timeout=self.timeout,
            )

            logger.info(f"Saved pipeline to {response.pipeline_path}")
            return {
                "success": response.success,
                "pipeline_path": response.pipeline_path,
                "weights_path": response.weights_path if response.weights_path else None,
            }

        except grpc.RpcError as e:
            logger.error(f"Failed to save pipeline: {e.details()}")
            raise RuntimeError(f"Failed to save pipeline: {e.details()}") from e

    def get_pipeline_inputs(self) -> dict[str, Any]:
        """Get current pipeline input specifications.

        Returns
        -------
        dict[str, Any]
            Dict with keys:
            - input_names (list[str]): Input port names
            - input_specs (dict): name → spec dict (dtype, shape, required)

        Raises
        ------
        RuntimeError
            If not connected or RPC fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            response = self.stub.GetPipelineInputs(
                cuvis_ai_pb2.GetPipelineInputsRequest(session_id=self.session_id),
                timeout=self.timeout,
            )

            # Convert TensorSpec to dict
            input_specs = {}
            for name, spec in response.input_specs.items():
                input_specs[name] = {
                    "name": spec.name,
                    "shape": list(spec.shape),
                    "dtype": cuvis_ai_pb2.DType.Name(spec.dtype),
                    "required": spec.required,
                }

            return {
                "input_names": list(response.input_names),
                "input_specs": input_specs,
            }

        except grpc.RpcError as e:
            logger.error(f"Failed to get pipeline inputs: {e.details()}")
            raise RuntimeError(f"Failed to get pipeline inputs: {e.details()}") from e

    def get_pipeline_outputs(self) -> dict[str, Any]:
        """Get current pipeline output specifications.

        Returns
        -------
        dict[str, Any]
            Dict with keys:
            - output_names (list[str]): Output port names
            - output_specs (dict): name → spec dict (dtype, shape)

        Raises
        ------
        RuntimeError
            If not connected or RPC fails
        """
        if not self._connected or not self.stub or not self.session_id:
            raise RuntimeError("Not connected to server or no active session")

        try:
            response = self.stub.GetPipelineOutputs(
                cuvis_ai_pb2.GetPipelineOutputsRequest(session_id=self.session_id),
                timeout=self.timeout,
            )

            # Convert TensorSpec to dict
            output_specs = {}
            for name, spec in response.output_specs.items():
                output_specs[name] = {
                    "name": spec.name,
                    "shape": list(spec.shape),
                    "dtype": cuvis_ai_pb2.DType.Name(spec.dtype),
                }

            return {
                "output_names": list(response.output_names),
                "output_specs": output_specs,
            }

        except grpc.RpcError as e:
            logger.error(f"Failed to get pipeline outputs: {e.details()}")
            raise RuntimeError(f"Failed to get pipeline outputs: {e.details()}") from e

    # Context Manager Support
    # -----------------------

    def __enter__(self) -> "CuvisAIClient":
        """Enter context manager (connects to server)."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager (disconnects from server)."""
        self.disconnect()

    # Properties
    # ----------

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected

    def __repr__(self) -> str:
        """String representation of client."""
        status = "connected" if self._connected else "disconnected"
        session = f", session={self.session_id}" if self.session_id else ""
        return f"CuvisAIClient({self.host}:{self.port}, {status}{session})"
