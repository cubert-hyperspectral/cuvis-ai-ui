# Cuvis.AI UI

[![CI Status](https://github.com/cubert-hyperspectral/cuvis-ai-ui/actions/workflows/ci.yml/badge.svg)](https://github.com/cubert-hyperspectral/cuvis-ai-ui/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/cubert-hyperspectral/cuvis-ai-ui/branch/main/graph/badge.svg)](https://codecov.io/gh/cubert-hyperspectral/cuvis-ai-ui)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

Visual pipeline editor for [cuvis-ai](https://github.com/cubert-hyperspectral/cuvis-ai). Build, edit, and manage hyperspectral processing pipelines through a drag-and-drop interface connected to a cuvis-ai-core gRPC server.

## Features

- Drag-and-drop pipeline editor with type-safe node connections
- Node palette with search and categorized browsing
- Property editor with dynamic parameter forms
- Load/save pipeline YAML files
- Plugin manager for extending available nodes
- Server connection dialog (local auto-start or remote)

## Quick Start

### Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- [cuvis-ai-core](https://github.com/cubert-hyperspectral/cuvis-ai-core) gRPC server

### Install and Run

```bash
git clone https://github.com/cubert-hyperspectral/cuvis-ai-ui.git
cd cuvis-ai-ui
uv sync
```

Start the [cuvis-ai-core](https://github.com/cubert-hyperspectral/cuvis-ai-core) gRPC server (in a separate terminal):

```bash
cd path/to/cuvis-ai-core
uv run python -m cuvis_ai_core.grpc.production_server
```

Launch the UI:

```bash
uv run cuvis-ui
```

## Windows Installer

A standalone Windows installer can be built that bundles both the UI and the gRPC server (including PyTorch CUDA 12.8) into a single setup executable.

### Prerequisites

- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- cuvis-ai-core venv with PyTorch CUDA 12.8

### Build

```cmd
installer\build.bat
```

Output: `installer\Output\cuvis-ai-ui-setup-<version>.exe`

The installed application auto-starts a local gRPC server. Users can also configure a remote server via **Tools > Connect to Server**.

## Configuration

Settings are stored in the platform-specific app config directory:

| Setting | File | Description |
|---------|------|-------------|
| Plugins | `plugin_settings.json` | Plugin catalog paths and enabled state |
| Connection | `connection.json` | Server mode (local/remote), host, port |

On Windows: `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\`

## License

Apache License 2.0 - [Cubert GmbH](https://cubert-gmbh.com)
