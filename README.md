# cuvis-ai-ui

Interactive pipeline visualization tool for cuvis-ai-core.

## Features

- Visual pipeline editor (drag-and-drop)
- Type-safe node connections with port validation
- Load and edit existing pipeline YAML files
- Save pipelines back to YAML format
- Integration with cuvis-ai-core via gRPC

## Requirements

- Python 3.11
- cuvis-ai-core gRPC server running
- uv (package manager)

## Installation

```bash
# Clone repository
git clone <repo-url>
cd cuvis-ai-ui

# Install dependencies
uv sync

# Generate gRPC stubs (if not already generated)
uv run python -m grpc_tools.protoc \
    --proto_path=proto \
    --python_out=cuvis_ai_ui/grpc \
    --grpc_python_out=cuvis_ai_ui/grpc \
    --pyi_out=cuvis_ai_ui/grpc \
    proto/cuvis_ai_core/grpc/v1/cuvis_ai_core.proto
```

## Usage

### Start cuvis-ai-core server

```bash
cd path/to/cuvis-ai-core
uv run python -m cuvis_ai_core.grpc.production_server
```

### Launch visualizer

```bash
uv run cuvis-ui
```

Or for development:

```bash
uv run python -m cuvis_ai_ui.main
```

## Development

### Running tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit -v

# Integration tests (requires server running)
uv run pytest tests/integration -v

# With coverage
uv run pytest --cov=cuvis_ai_ui --cov-report=html
```

### Code quality

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy cuvis_ai_ui
```

## Project Structure

```
cuvis-ai-ui/
├── cuvis_ai_ui/
│   ├── __init__.py
│   ├── main.py                    # CLI entry point
│   ├── main_window.py             # Qt MainWindow
│   ├── grpc/
│   │   ├── __init__.py
│   │   ├── v1/                    # Generated protobuf stubs
│   │   └── client.py              # CuvisAIClient wrapper
│   ├── adapters/
│   │   ├── node_adapter.py        # CuvisNodeAdapter (NodeGraphQt wrapper)
│   │   ├── pipeline_serializer.py # YAML ↔ NodeGraphQt converter
│   │   └── port_mapper.py         # PortSpec → NodeGraphQt port mapping
│   └── widgets/
│       ├── node_palette.py        # Node catalog (Phase 2)
│       ├── property_editor.py     # Parameter editor (Phase 2)
│       └── plugin_manager.py      # Plugin loader (Phase 2)
├── tests/
│   ├── unit/                      # Pure logic tests
│   ├── integration/               # gRPC integration tests
│   └── manual/                    # Manual test workflows
├── docs/
├── proto/                         # Proto files from cuvis-ai-core
└── pyproject.toml
```

## Implementation Status

### ✅ Phase 1: Core Infrastructure (Complete)
- [x] Project setup with uv
- [x] gRPC client implementation ([client.py](cuvis_ai_ui/grpc/client.py))
- [x] Connection management with retry logic
- [x] Session lifecycle management
- [x] Node discovery API
- [x] Port mapper with type validation ([port_mapper.py](cuvis_ai_ui/adapters/port_mapper.py))
- [x] Node adapter for NodeGraphQt ([node_adapter.py](cuvis_ai_ui/adapters/node_adapter.py))
- [x] Pipeline serializer YAML ↔ Graph ([pipeline_serializer.py](cuvis_ai_ui/adapters/pipeline_serializer.py))
- [x] Qt MainWindow with NodeGraphQt canvas ([main_window.py](cuvis_ai_ui/main_window.py))

### ✅ Phase 2: Enhanced UX & Discovery (Complete)
- [x] Node palette with search and drag-drop ([node_palette.py](cuvis_ai_ui/widgets/node_palette.py))
- [x] Property editor with dynamic forms ([property_editor.py](cuvis_ai_ui/widgets/property_editor.py))
- [x] Plugin manager dialog ([plugin_manager.py](cuvis_ai_ui/widgets/plugin_manager.py))
- [x] Session management dialog

### ⏳ Phase 3: Execution & Results (Pending)
- [ ] Inference input configuration
- [ ] Training workflow UI
- [ ] Result visualization
- [ ] Real-time progress display

**Overall Progress**: Phase 2 Complete (66%)

## Testing

### Quick Test (30 seconds)
See [QUICKSTART.md](QUICKSTART.md) for immediate testing instructions.

### Comprehensive Testing
See [TESTING.md](TESTING.md) for detailed test scenarios including:
- Connection and session management
- Node discovery
- Pipeline operations
- Error handling
- Troubleshooting guide

## Documentation

- **Quick Start**: [QUICKSTART.md](QUICKSTART.md) - Test current implementation
- **Testing Guide**: [TESTING.md](TESTING.md) - Comprehensive test scenarios
- **Implementation Plan**: [C:\Users\nima.ghorbani\.claude\plans\functional-greeting-pond.md](C:\Users\nima.ghorbani\.claude\plans\functional-greeting-pond.md)
- **Blueprint**: [D:\code-repos\dev-docs\ALL_5170\ALL_5170_cuvis_ai_nodegraphqt_blueprint.md](D:\code-repos\dev-docs\ALL_5170\ALL_5170_cuvis_ai_nodegraphqt_blueprint.md)

## License

Apache License 2.0

## Authors

Cubert GmbH - cuvis.ai@cubert-gmbh.com
