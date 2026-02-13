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

    # Mock RPC error
    mock_error = Mock(spec=grpc.RpcError)
    mock_error.code.return_value = grpc.StatusCode.UNAVAILABLE
    mock_error.details.return_value = "Connection refused"

    mock_stub = Mock()
    mock_stub.CreateSession.side_effect = mock_error
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
