![image](https://github.com/cubert-hyperspectral/cuvis.sdk/blob/main/branding/logo/banner.png?raw=true)

# Cuvis.AI UI

[![CI][ci-badge]][ci-link]
[![codecov][cov-badge]][cov-link]
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

[ci-badge]: https://img.shields.io/github/actions/workflow/status/cubert-hyperspectral/cuvis-ai-ui/ci.yml?style=flat-square&logo=githubactions&logoColor=white&label=CI
[ci-link]: https://github.com/cubert-hyperspectral/cuvis-ai-ui/actions/workflows/ci.yml
[cov-badge]: https://img.shields.io/codecov/c/github/cubert-hyperspectral/cuvis-ai-ui?style=flat-square&logo=codecov&logoColor=white
[cov-link]: https://codecov.io/gh/cubert-hyperspectral/cuvis-ai-ui

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
uv sync --all-exrtas
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

A standalone Windows installer can be built that ships the UI as a frozen PyInstaller bundle and the cuvis-ai-core source. Heavy runtime dependencies (PyTorch CUDA 12.8, FFmpeg, Graphviz, etc.) install at **install-time** via `uv sync` and direct downloads — keeping the installer ~150 MB and the build ~3 minutes.

### Prerequisites for building

- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- cuvis-ai-core checked out as a sibling at `..\..\cuvis-ai-core\cuvis-ai-core\`
- A populated cuvis-ai-ui venv (`uv sync --extra dev`)

### Build

```cmd
installer\build.bat
```

Output: `installer\Output\cuvis-ai-ui-setup-<version>.exe` (~150 MB)

### What the installer does at install time

The Inno Setup wizard exposes a checkbox **"Install the local cuvis-ai-core gRPC server (~3 GB download)"** under "Server runtime:". Uncheck it if the user only wants the UI (e.g. to connect to a remote server). When checked, `installer\bootstrap.ps1` runs at the end of Inno Setup and does what the [cuvis-ai install guide](https://cubert-hyperspectral.github.io/cuvis-ai-docs-revision/user-guide/installation/) tells a developer to do, in one shot:

1. Installs `uv` if not on PATH (`irm https://astral.sh/uv/install.ps1 | iex`).
2. Copies the shipped cuvis-ai-core source to `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server\source\`.
3. `uv venv --python 3.11` at `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server-venv\`, then `uv sync` against the source — pulls cuvis-ai-core, torch CUDA 12.8 (via `[tool.uv.sources]`), cuvis-ai-schemas, the cuvis SDK Python binding, etc.
4. `uv pip install pystray` for the tray icon.
5. Downloads FFmpeg LGPL shared + Graphviz portable into `{app}\ffmpeg\` and `{app}\graphviz\`.

Logs go to `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\bootstrap.log`. The bootstrap is idempotent — re-running it (e.g. via the **Setup local server** Start Menu shortcut after opting out at install time) reuses the existing venv, skips already-downloaded binaries, and only does work that's missing. The Cuvis SDK is still a separate manual install — the installer prompts with the download link at the end.

### Launching the installed app

The server is a separate windowless tray process; start it manually before opening the UI:

1. Start menu → **Cuvis.AI UI** → **Cuvis.AI Server** — a green-dot icon appears in the system tray once the server binds `localhost:50051`. Cold start with CUDA + cuvis SDK can take ~30 s.
2. Start menu → **Cuvis.AI UI** → **Cuvis.AI UI** — the UI TCP-probes the port; if no server is up, it shows a dialog pointing back to step 1.
3. Right-click the tray icon for **Open log…**, **Open data folder…**, or **Quit**. Logs at `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server.log`.

To switch to a remote server (or opt back into legacy auto-start), open **Tools → Connect to Server** inside the UI.

### Adding new plugins after install

Plugin Manager → add a plugin → the server runs `uv pip install` against the same `server-venv`, so deps land alongside cuvis-ai-core's. No special plumbing needed: `cuvis-ai-core/utils/git_and_os.py:_install_dependencies_with_uv` Just Works because the server is running in a normal venv.

### What's bundled vs. installed separately

| Component | Bundled in installer? | Notes |
| --- | --- | --- |
| Cuvis.AI UI | yes | PyInstaller `dist\cuvis-ui\` |
| cuvis-ai-core gRPC server (incl. PyTorch CUDA 12.8) | yes | PyInstaller `dist\cuvis-server\` |
| FFmpeg (shared, LGPL) | yes | `{app}\ffmpeg\bin` — torchcodec / `ToVideoNode` use it |
| Graphviz | yes | `{app}\graphviz\bin` — `pipeline.visualize(format="png"/"svg")` uses `dot` |
| `cuvis-ai` node catalog | fetched on first launch | `cuvis_ai_catalog.yaml` clones `cubert-hyperspectral/cuvis-ai` at the pinned tag into the per-user plugin cache |
| **Cuvis SDK** (C++ shared lib for `.cu3s` / `.cu3` I/O) | **no — install separately** | The post-install dialog links to the [Cubert SDK download page](https://cloud.cubert-gmbh.de/s/qpxkyWkycrmBK9m). Without it any cube read fails at runtime. |

## Configuration

Settings are stored in the platform-specific app config directory:

| Setting | File | Description |
|---------|------|-------------|
| Plugins | `plugin_settings.json` | Plugin catalog paths and enabled state |
| Connection | `connection.json` | Server mode (local/remote), host, port |

On Windows: `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\`

## License

Apache License 2.0 - [Cubert GmbH](https://cubert-gmbh.com)
