"""Tests for gRPC client wrapper."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from cuvis_ai_ui.grpc.client import CuvisAIClient, _dtype_to_string, _convert_port_specs


@pytest.fixture
def mock_grpc_stub():
    """Mock gRPC stub for testing."""
    stub = Mock()

    # Mock session response
    session_response = Mock()
    session_response.session_id = "test-session-123"
    session_response.success = True
    stub.CreateSession.return_value = session_response
    stub.CloseSession.return_value = Mock(success=True)

    return stub


def test_client_initialization():
    """Test CuvisAIClient initialization."""
    client = CuvisAIClient(host="localhost", port=50051, timeout=30)

    assert client.host == "localhost"
    assert client.port == 50051
    assert client.timeout == 30
    assert client.channel is None
    assert client.stub is None
    assert client.session_id is None
    assert not client._connected


def test_client_initialization_with_defaults():
    """Test CuvisAIClient initialization with default parameters."""
    client = CuvisAIClient()

    assert client.host == "localhost"
    assert client.port == 50051
    assert client.timeout == 30
    assert client.max_retries == 3


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_connect_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test successful connection to gRPC server."""
    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    result = client.connect()

    assert result is True
    assert client._connected
    assert client.session_id == "test-session-123"
    mock_channel.assert_called_once()


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_connect_failure_raises_connection_error(mock_stub_class, mock_channel):
    """Test connection failure raises ConnectionError after retries."""
    import grpc

    # Create a proper exception subclass with code()/details() methods
    class _MockRpcError(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.UNAVAILABLE

        def details(self):
            return "Connection refused"

    mock_stub = Mock()
    mock_stub.CreateSession.side_effect = _MockRpcError()
    mock_stub_class.return_value = mock_stub
    mock_channel.return_value = Mock()

    client = CuvisAIClient(max_retries=1)  # Reduce retries for faster test

    with pytest.raises(ConnectionError, match="Failed to connect"):
        client.connect()


def test_disconnect_when_not_connected():
    """Test disconnecting when not connected."""
    client = CuvisAIClient()

    result = client.disconnect()

    assert result is True


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_disconnect_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test successful disconnection."""
    mock_channel_instance = Mock()
    mock_channel.return_value = mock_channel_instance
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()
    result = client.disconnect()

    assert result is True
    assert not client._connected
    mock_channel_instance.close.assert_called_once()


def test_create_session_not_connected_raises_error():
    """Test creating session when not connected raises RuntimeError."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.create_session()


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_create_session_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test creating a new session."""
    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    # Call create_session again
    session_id = client.create_session()

    assert session_id == "test-session-123"


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_close_session(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test closing a session."""
    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.close_session()

    assert result is True
    assert client.session_id is None


def test_close_session_without_session():
    """Test closing session when no session exists."""
    client = CuvisAIClient()

    result = client.close_session()

    assert result is True


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_context_manager(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test using client as context manager."""
    mock_channel_instance = Mock()
    mock_channel.return_value = mock_channel_instance
    mock_stub_class.return_value = mock_grpc_stub

    with CuvisAIClient() as client:
        assert client._connected
        assert client.session_id is not None

    # After context, should be disconnected
    mock_channel_instance.close.assert_called_once()


def test_load_plugins_not_connected_raises_error():
    """Test loading plugins when not connected raises error."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.load_plugins(Path("test.yaml"))


def test_dtype_to_string():
    """Test converting proto DType enum to string."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_FLOAT32) == "float32"
    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_FLOAT64) == "float64"
    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_INT32) == "int32"
    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_INT64) == "int64"
    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_BOOL) == "bool"


def test_dtype_to_string_unknown():
    """Test converting unknown dtype returns 'unknown'."""
    assert _dtype_to_string(999) == "unknown"


def test_convert_port_specs():
    """Test converting proto port specs to dicts."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    # Create mock port spec
    mock_spec = Mock()
    mock_spec.name = "test_port"
    mock_spec.dtype = cuvis_ai_pb2.D_TYPE_FLOAT32
    mock_spec.shape = [-1, -1, -1]
    mock_spec.optional = False
    mock_spec.description = "Test port"

    mock_port_spec_list = Mock()
    mock_port_spec_list.specs = [mock_spec]

    port_specs_map = {"port1": mock_port_spec_list}

    result = _convert_port_specs(port_specs_map)

    assert len(result) == 1
    assert result[0]["name"] == "test_port"
    assert result[0]["dtype"] == "float32"
    assert result[0]["optional"] is False
    assert result[0]["description"] == "Test port"


def test_convert_port_specs_with_empty_name():
    """Test converting port specs uses port name from map if spec name is empty."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    mock_spec = Mock()
    mock_spec.name = ""  # Empty name
    mock_spec.dtype = cuvis_ai_pb2.D_TYPE_FLOAT32
    mock_spec.shape = []
    mock_spec.optional = False
    mock_spec.description = ""

    mock_port_spec_list = Mock()
    mock_port_spec_list.specs = [mock_spec]

    port_specs_map = {"fallback_name": mock_port_spec_list}

    result = _convert_port_specs(port_specs_map)

    assert result[0]["name"] == "fallback_name"


def test_convert_port_specs_empty_shape():
    """Test converting port specs with empty shape."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    mock_spec = Mock()
    mock_spec.name = "test"
    mock_spec.dtype = cuvis_ai_pb2.D_TYPE_FLOAT32
    mock_spec.shape = []
    mock_spec.optional = False
    mock_spec.description = ""

    mock_port_spec_list = Mock()
    mock_port_spec_list.specs = [mock_spec]

    result = _convert_port_specs({"test": mock_port_spec_list})

    assert result[0]["shape"] == "any"


# ---------------------------------------------------------------------------
# Additional coverage: disconnect error handling
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_disconnect_handles_error(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test disconnect handles errors gracefully."""
    mock_channel_instance = Mock()
    mock_channel_instance.close.side_effect = Exception("Close failed")
    mock_channel.return_value = mock_channel_instance
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()
    result = client.disconnect()

    assert result is False


# ---------------------------------------------------------------------------
# Additional coverage: close_session RPC error
# ---------------------------------------------------------------------------


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_close_session_rpc_error(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test close_session handles gRPC error."""
    import grpc

    class _MockRpcError(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.INTERNAL

        def details(self):
            return "Session close failed"

    mock_grpc_stub.CloseSession.side_effect = _MockRpcError()
    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()
    result = client.close_session()

    assert result is False


# ---------------------------------------------------------------------------
# Additional coverage: is_connected property, repr
# ---------------------------------------------------------------------------


def test_is_connected_property():
    """Test is_connected property."""
    client = CuvisAIClient()
    assert client.is_connected is False

    client._connected = True
    assert client.is_connected is True


# ---------------------------------------------------------------------------
# Additional coverage: list_available_nodes
# ---------------------------------------------------------------------------


def test_list_nodes_not_connected_raises_error():
    """Test listing nodes when not connected raises RuntimeError."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.list_available_nodes()


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_list_available_nodes_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test listing available nodes successfully."""

    # Mock node info in response
    mock_node = Mock()
    mock_node.class_name = "MinMaxNormalizer"
    mock_node.full_path = "cuvis_ai.node.normalization.MinMaxNormalizer"
    mock_node.source = "builtin"
    mock_node.plugin_name = ""
    mock_node.input_specs = {}
    mock_node.output_specs = {}

    mock_response = Mock()
    mock_response.nodes = [mock_node]
    mock_grpc_stub.ListAvailableNodes.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    nodes = client.list_available_nodes()

    assert len(nodes) == 1
    assert nodes[0]["class_name"] == "MinMaxNormalizer"
    assert nodes[0]["full_path"] == "cuvis_ai.node.normalization.MinMaxNormalizer"


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_list_available_nodes_rpc_error(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test listing nodes with RPC error."""
    import grpc

    class _MockRpcError(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.INTERNAL

        def details(self):
            return "List failed"

    mock_grpc_stub.ListAvailableNodes.side_effect = _MockRpcError()
    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    with pytest.raises(RuntimeError, match="Failed to list nodes"):
        client.list_available_nodes()


# ---------------------------------------------------------------------------
# Additional coverage: resolve_config
# ---------------------------------------------------------------------------


def test_resolve_config_not_connected_raises_error():
    """Test resolve_config when not connected raises RuntimeError."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.resolve_config("pipeline", "test.yaml")


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_resolve_config_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test resolving config successfully."""
    import json

    mock_response = Mock()
    mock_response.config_bytes = json.dumps({"key": "value"}).encode()
    mock_grpc_stub.ResolveConfig.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.resolve_config("pipeline", "test.yaml", overrides=["lr=0.01"])

    assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# Additional coverage: load_pipeline, save_pipeline
# ---------------------------------------------------------------------------


def test_load_pipeline_not_connected_raises_error():
    """Test load_pipeline when not connected raises RuntimeError."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.load_pipeline({"metadata": {}, "nodes": [], "connections": []})


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_load_pipeline_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test loading pipeline successfully."""
    mock_response = Mock()
    mock_response.success = True
    mock_response.metadata = Mock()
    mock_response.metadata.name = "Test Pipeline"
    mock_response.metadata.description = "A test"
    mock_response.metadata.tags = ["test"]
    mock_grpc_stub.LoadPipeline.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.load_pipeline({"metadata": {"name": "Test"}, "nodes": [], "connections": []})

    assert result["success"] is True
    assert result["metadata"]["name"] == "Test Pipeline"


def test_save_pipeline_not_connected_raises_error():
    """Test save_pipeline when not connected raises RuntimeError."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.save_pipeline("output.yaml")


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_save_pipeline_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test saving pipeline successfully."""
    mock_response = Mock()
    mock_response.success = True
    mock_response.pipeline_path = "/output/pipeline.yaml"
    mock_response.weights_path = ""
    mock_grpc_stub.SavePipeline.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.save_pipeline(
        "output.yaml", metadata={"name": "Test", "description": "desc", "tags": ["a"]}
    )

    assert result["success"] is True
    assert result["pipeline_path"] == "/output/pipeline.yaml"


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_save_pipeline_no_metadata(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test saving pipeline without metadata."""
    mock_response = Mock()
    mock_response.success = True
    mock_response.pipeline_path = "/output/pipeline.yaml"
    mock_response.weights_path = "/output/weights.pt"
    mock_grpc_stub.SavePipeline.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.save_pipeline("output.yaml")

    assert result["success"] is True
    assert result["weights_path"] == "/output/weights.pt"


# ---------------------------------------------------------------------------
# Additional coverage: get_pipeline_inputs / outputs
# ---------------------------------------------------------------------------


def test_get_pipeline_inputs_not_connected():
    """Test get_pipeline_inputs when not connected."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.get_pipeline_inputs()


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_get_pipeline_inputs_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test getting pipeline inputs."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    mock_spec = Mock()
    mock_spec.name = "cube"
    mock_spec.shape = [-1, -1, -1, -1]
    mock_spec.dtype = cuvis_ai_pb2.D_TYPE_FLOAT32
    mock_spec.required = True

    mock_response = Mock()
    mock_response.input_names = ["cube"]
    mock_response.input_specs = {"cube": mock_spec}
    mock_grpc_stub.GetPipelineInputs.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.get_pipeline_inputs()

    assert result["input_names"] == ["cube"]
    assert "cube" in result["input_specs"]


def test_get_pipeline_outputs_not_connected():
    """Test get_pipeline_outputs when not connected."""
    client = CuvisAIClient()

    with pytest.raises(RuntimeError, match="Not connected"):
        client.get_pipeline_outputs()


@patch("cuvis_ai_ui.grpc.client.grpc.insecure_channel")
@patch("cuvis_ai_ui.grpc.client.cuvis_ai_pb2_grpc.CuvisAIServiceStub")
def test_get_pipeline_outputs_success(mock_stub_class, mock_channel, mock_grpc_stub):
    """Test getting pipeline outputs."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    mock_spec = Mock()
    mock_spec.name = "prediction"
    mock_spec.shape = [-1, 10]
    mock_spec.dtype = cuvis_ai_pb2.D_TYPE_FLOAT32

    mock_response = Mock()
    mock_response.output_names = ["prediction"]
    mock_response.output_specs = {"prediction": mock_spec}
    mock_grpc_stub.GetPipelineOutputs.return_value = mock_response

    mock_channel.return_value = Mock()
    mock_stub_class.return_value = mock_grpc_stub

    client = CuvisAIClient()
    client.connect()

    result = client.get_pipeline_outputs()

    assert result["output_names"] == ["prediction"]
    assert "prediction" in result["output_specs"]


# ---------------------------------------------------------------------------
# Additional coverage: additional dtype conversions
# ---------------------------------------------------------------------------


def test_dtype_to_string_all_types():
    """Test converting all defined dtype enums."""
    from cuvis_ai_schemas.grpc.v1 import cuvis_ai_pb2

    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_UINT8) == "uint8"
    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_FLOAT16) == "float16"
    assert _dtype_to_string(cuvis_ai_pb2.D_TYPE_UINT16) == "uint16"
