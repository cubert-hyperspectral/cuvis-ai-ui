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
- Node palette with search and categorized browsing, filled with the nodes of every
  released cuvis-ai plugin (bundled catalog)
- Pipeline folders: open a folder and step through its pipelines in the Pipelines dock
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
uv sync --all-extras
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

### Command line

```bash
uv run cuvis-ui path/to/pipelines                 # a folder: Pipelines dock, first pipeline open
uv run cuvis-ui path/to/pipeline.yaml             # one pipeline
uv run cuvis-ui path/to/pipelines --start-server  # start the local server first if none is running
uv run cuvis-ui --plugins-dir path/to/manifests   # register more plugin manifests (repeatable)
```

With `--start-server` (or local mode with auto-start in **Tools > Connect to Server**) the UI
starts the server itself. It uses the first of: the per-user server-venv the installer creates,
`<repos>/cuvis-ai-core/cuvis-ai-core/.venv` when this checkout sits at
`<repos>/cuvis-ai-ui/<checkout>`, or its own interpreter if `cuvis_ai_core` imports there. The server's output goes to `server.log` in the per-user data
folder (`%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\` on Windows).

While the UI waits for a starting server (up to 120 s), connects or registers plugins, a progress
dialog with a **Cancel** button stays on screen and the windows keep repainting. Cancel takes effect
at the next step: a server that is starting keeps starting (**Tools > Connect to Server** picks it
up), and a cancelled plugin registration leaves the palette empty until **Tools > Refresh Nodes**.

### Plugins

The palette lists the nodes of every registered plugin manifest. The UI registers, in this
order, with a later manifest of the same name replacing an earlier one:

1. the bundled catalog in `cuvis_ai_ui/catalog/`: the released plugin manifests of cuvis-ai
   (see its `README.md` for the tag),
2. plugins added in **Tools > Manage Plugins** (`plugins.json`),
3. the `*.yaml` manifests in the app's `plugins/` folder in the config directory,
4. each `--plugins-dir` folder,
5. the `plugins/` subfolder of the open pipelines folder.

A plugin disabled in the Plugin Manager stays disabled whichever folder supplies it. Manifests
are bare plugin manifests as in cuvis-ai's `cuvis_ai/configs/plugins/`; a relative local `path:`
is resolved against the manifest file. Registering a manifest is metadata only: the server builds
the palette entries from its `capabilities` and installs the plugin only when a pipeline that
uses it runs. Opening another folder or changing plugins starts a fresh server session, so
plugins from the previous folder are gone.

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
2. Copies the shipped cuvis-ai-core source to `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server\source\`. The source has no `.git`; `build.bat` wrote its version into its `pyproject.toml` (setuptools-scm `fallback_version`), so this install and every environment the server later builds from the source resolve it.
3. `uv venv --python 3.11` at `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server-venv\`, then `uv sync` against the source: cuvis-ai-core, torch CUDA 12.8 (via `[tool.uv.sources]`), cuvis-ai-schemas and their dependencies.
4. `uv pip install pystray` for the tray icon.
5. Downloads FFmpeg LGPL shared + Graphviz portable into `{app}\ffmpeg\` and `{app}\graphviz\`.

Logs go to `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\bootstrap.log`. The bootstrap is idempotent — re-running it (e.g. via the **Setup local server** Start Menu shortcut after opting out at install time) reuses the existing venv, skips already-downloaded binaries, and only does work that's missing. The Cuvis SDK is still a separate manual install — the installer prompts with the download link at the end.

### Launching the installed app

The server is a separate windowless tray process; start it manually before opening the UI:

1. Start menu > **Cuvis.AI UI** > **Cuvis.AI Server**: a green-dot icon appears in the system tray once the server binds `localhost:50051`. Cold start with CUDA can take about 30 s. Alternatively start the UI as `cuvis-ui.exe <folder> --start-server`, which starts the server from the same server-venv.
2. Start menu → **Cuvis.AI UI** → **Cuvis.AI UI** — the UI TCP-probes the port; if no server is up, it shows a dialog pointing back to step 1.
3. Right-click the tray icon for **Open log…**, **Open data folder…**, or **Quit**. Logs at `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server.log`.

To switch to a remote server (or opt back into legacy auto-start), open **Tools → Connect to Server** inside the UI.

### Adding new plugins after install

Put the manifest in the app's `plugins/` folder (or a pipelines folder's `plugins/` subfolder), or add it in **Tools > Manage Plugins**. The palette shows its nodes right away. When a pipeline that uses the plugin runs, the server prepares (or reuses) a separate cached environment with the pipeline's plugins.

### What's bundled vs. installed separately

| Component | Bundled in installer? | Notes |
| --- | --- | --- |
| Cuvis.AI UI | yes | PyInstaller `dist\cuvis-ui\` |
| cuvis-ai-core gRPC server (incl. PyTorch CUDA 12.8) | installed at install time | `bootstrap.ps1` creates the per-user `server-venv` from the shipped core source (tag in `.cuvis-ai-core-version`) |
| FFmpeg (shared, LGPL) | yes | `{app}\ffmpeg\bin` — torchcodec / `ToVideoNode` use it |
| Graphviz | yes | `{app}\graphviz\bin` — `pipeline.visualize(format="png"/"svg")` uses `dot` |
| cuvis-ai plugin catalog | yes | `cuvis_ai_ui\catalog\`: the released plugin manifests; each plugin lands in a per-pipeline cached environment when a pipeline that uses it runs |
| **Cuvis SDK** (C++ shared lib for `.cu3s` / `.cu3` I/O) | **no, install separately** | Only needed to read cubes, through the cuvis-ai-dataloader plugin; drawing and editing pipelines works without it. The post-install dialog links to the [Cubert SDK download page](https://cloud.cubert-gmbh.de/s/qpxkyWkycrmBK9m). |

## Configuration

Settings are stored in the platform-specific app config directory:

| Setting | File | Description |
|---------|------|-------------|
| Plugins | `plugins.json` | Plugins added in the Plugin Manager, and enabled flags |
| Plugin manifests | `plugins\*.yaml` | Extra plugin manifests registered at every start |
| Connection | `connection.json` | Server mode (local/remote), host, port, auto-start |

On Windows: `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\`

## License

Apache License 2.0 - [Cubert GmbH](https://cubert-gmbh.com)
