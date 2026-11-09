# Changelog

## 0.5.2 - 2026-11-09

- The Test button in Tools > Connect to Server closes its gRPC channel when the test fails too, not only when it connects.

## 0.5.1 - 2026-11-08

- Nodes on the canvas show their class on a second, smaller line under the node name.
- Starting the local server, connecting and registering plugins no longer freeze the window. Each runs behind a progress dialog with a Cancel button: at startup, on a folder switch, in the Plugin Manager and on Tools > Connect to Server. Cancel takes effect at the next step; a server that is starting keeps starting, and a cancelled registration empties the palette until Tools > Refresh Nodes.
- Cancel on Tools > Connect to Server keeps the current connection if it comes before that connection is closed and the switch has not stopped the local server it used; otherwise the window says it is not connected.
- The installer writes the cuvis-ai-core version into the source it ships (setuptools-scm `fallback_version`), so environments the installed server builds from that source get a version. After upgrading, run Start menu > Cuvis.AI UI > Setup local server once, or install with the server option, to refresh the copied source. A core worktree's `.git` file is no longer copied into the installer, and the server setup skips one that an older installer left behind.
- Waiting for the server, failed connect attempts and a Cancel that drops the client of a stopped local server no longer leave gRPC channels open.
- The tray launcher redirects its output only when it runs, and a test keeps its per-user data folder in step with the UI's.

## 0.5.0 - 2026-11-07

- The node palette lists the nodes of every released cuvis-ai plugin: the bundled catalog `cuvis_ai_ui/catalog/` holds the 18 git-pinned plugin manifests of cuvis-ai v0.22.6 (247 nodes), replaces `cuvis_ai_catalog.yaml`, and ships in the wheel and the installer. `scripts/regenerate_catalog.py --tag <tag>` mirrors a newer release.
- Bundled plugins always come from the installed catalog and `plugins.json` keeps only their enabled flag, so a store written by an older version no longer hides new plugins; a user plugin that happens to come from a file named `cuvis_ai_catalog.yaml` stays a user plugin, and a disabled flag stored under the builtin plugin's earlier name `cuvis_ai_catalog` carries over. Removing a bundled plugin in the Plugin Manager disables it. `plugins.json` is written in one step, so a value it cannot hold no longer leaves a truncated store, and an unquoted date in a manifest is stored as text.
- `cuvis-ui PATH` opens a pipeline file or a folder of pipelines. A folder fills the new Pipelines dock (also File > Open Folder) and registers the manifests in its `plugins/` subfolder; `--plugins-dir` adds manifest folders, and the app's own `plugins/` folder is read at every start. The Plugin Manager lists plugins from these folders as read-only rows.
- `--start-server` starts the local server for the run. The UI looks for the per-user server-venv, then the `.venv` of a cuvis-ai-core checkout in the nested layout next to this one, then its own interpreter, and writes the server's output to `server.log` instead of an unread pipe that could stall the server. A log that cannot be written is reported as a start error. Startup and Tools > Connect to Server reuse a server that already listens and otherwise wait up to 120 s for the one they start; reconnecting while the UI's own server is still starting waits for it instead of starting a second one.
- Pipelines load with every edge: fan-in inputs keep all their connections, nodes whose manifest lists no ports take them from the connections, and the load warnings name each connection that could not be drawn and each `plugins:` entry the server does not know. A class named by its defining module (`pkg.node.module.Cls`, as cuvis-ai saves it) or by its bare name resolves to the registered class and keeps that name when saved. That fallback stays within the plugins the pipeline declares (plus the core built-ins), and a dotted name within its own package, so a node of a missing plugin stays a placeholder instead of taking a same-named class of another plugin.
- Saving keeps the plugin each node came from, so a pipeline saved after a folder switch still declares its plugins.
- Loaded pipelines are laid out by node size, so wide nodes no longer overlap, and each opened pipeline is framed in the view.
- A change of the plugin set (folder, Plugin Manager, refresh, reconnect) starts a fresh server session, replaces node types whose ports changed and removes those of plugins that are gone; the status bar names plugins that failed to load. The manifest is written before the old session closes, an unquoted date in a manifest (`tag: 2026-01-01`) is sent as text, and a registration that fails leaves no stale nodes on offer.
- Opening another pipeline asks about unsaved changes on every route and clears the Properties panel; graph and property edits mark the pipeline unsaved (selecting nodes does not), Save As updates the Pipelines dock, and a cancelled close keeps the server connection.
- Requires `cuvis-ai-schemas[proto]>=0.14.4`. The installer builds against cuvis-ai-core v0.20.2 (`CUVIS_AI_CORE_ROOT` points `build.bat` at another checkout), its bootstrap smoke test no longer imports the Cuvis SDK, and a silent install no longer stops on the Cuvis SDK question.

## 0.4.0 - 2026-11-05

- Regenerated `cuvis_ai_catalog.yaml` from cuvis-ai v0.21.0 (165 nodes, was v0.9.0): the palette gains every node added since, and `Standardize` replaces `ZScoreNormalizerGlobal`, `ZScoreNormalizer` and `ChannelNormalizeNode` in the catalog; cuvis-ai 0.21.0 also removed `MeanCenter`, `UnitVarianceScaling` and `SNVCorrection`, which this bundled manifest never exposed.

## 0.3.1 - 2026-07-17

- Raised the `cuvis-ai-schemas[proto]` floor to `>=0.8.0`, aligning the gRPC client with the released cuvis-ai-next contract. No code change: the UI consumes the static display tables and detects plugins via the gRPC `NodeInfo` fields.

## 0.3.0 - 2026-06-23

- Changed `cuvis_ai_ui/grpc/client.py` `load_plugins` to call the singular `LoadPlugin` RPC once per manifest (the batch `LoadPlugins` is gone) and to resolve each local plugin's relative `path` to an absolute path before sending, since the server cannot resolve a client-relative path. The returned dict keeps its `loaded_plugins` / `failed_plugins` keys so call sites are unaffected.
- Changed `cuvis_ai_catalog.yaml` `provides:` from bare class-name strings to inline `CatalogNodeEntry` objects (FQCN plus port specs, category, tags, icon SVG), so the node palette is populated from the manifest without the server importing plugin code; bumped the bundled catalog's cuvis-ai source tag to `v0.9.0`.
- Added `scripts/regenerate_catalog.py` to regenerate the bundled catalog from cuvis-ai's `configs/plugins/cuvis_ai_builtin.yaml`, normalising port specs to the single-`CatalogPortSpec`-per-port (`variadic` flag) shape. Idempotent; re-run with `--tag` for a new cuvis-ai release.
- Added `_coerce_provides` in `cuvis_ai_ui/settings/plugins.py` (applied in `build_manifest` and the Plugin Manager git/local loaders) to wrap bare class-name `provides:` entries into `{class_name: ...}` so manifests validate against the new schema. Updated the "Provided Nodes" help text: the palette is built from this list — the server no longer auto-discovers plugin nodes.
- Changed `pipeline_serializer.to_config` to emit a bare-name `plugins:` block derived from each node's owning plugin, as required by the loader's pipeline plugin resolver; classes with no known plugin are surfaced as a load warning.
- Changed `cuvis_ai_ui/adapters/port_helpers.py` and `widgets/node_palette.py` to use the renamed `PortSpec.variadic` field (was `multi_input`) for fan-in input ports; the palette tooltip now flags variadic ports.
- Changed the CLI surface to `click`: the `cuvis-ui` / `cuvis-ui-test` entry points and `scripts/regenerate_catalog.py` are now click commands with `--help` and options (`--test`, `--host`/`--port`, `--src`/`--dst`/`--repo`/`--tag`). Added `click` as a dependency.
- Changed the `cuvis-ai-schemas[proto]` floor from `>=0.4.0` to `>=0.7.0` to align with the ecosystem release. No code change: the UI consumes only the static `CATEGORY_STYLES` / `TAG_STYLES` tables from `node_display` (unchanged), and detects plugins from the gRPC `NodeInfo.source` / `plugin_name` fields rather than the registry's renamed `loaded_plugin_nodes` attribute.
- Removed the local `cuvis-ai-schemas` editable path source from `[tool.uv.sources]` (commented out): schemas `0.7.0` is published on PyPI, so clean checkouts resolve it from the index. Uncomment for local lockstep development against an on-disk checkout.
- Started tracking `uv.lock` (removed it from `.gitignore`) so dependency resolution is reproducible across checkouts and CI, matching `cuvis-ai` and `cuvis-ai-core`.

## 0.2.0 - 2026-05-18

- Added a `windows-installer` job to `.github/workflows/pypi-release.yml` that builds `cuvis-ai-ui-setup-<version>.exe` on `windows-latest` and attaches it to the GitHub Release alongside the wheel and tarball. The job invokes `installer\build.bat` unchanged; the `cuvis-ai-core` revision used for the build is pinned in a new `.cuvis-ai-core-version` file at the repo root (initial pin: `v0.6.0`).
- Added an opt-out checkbox to the Inno Setup wizard: **"Install the local cuvis-ai-core gRPC server (~3 GB download)"**. Unchecking it skips the bootstrap [Run] step and the `Cuvis.AI Server` Start Menu shortcut, leaving only the UI (useful when the user just wants to connect to a remote server). A new **"Setup local server"** Start Menu shortcut re-invokes `bootstrap.ps1` so users who opted out at install time can complete the setup later. The 3.5 MB cuvis-ai-core source + scripts are always shipped so the manual run is one click away.
- Pivoted the Windows installer from "bundle everything" to "install-time dependency resolution". The installer now ships only the UI PyInstaller bundle plus the cuvis-ai-core source tree (~150 MB total, was ~2 GB). A new `installer\bootstrap.ps1` runs at install time to (a) install `uv` if missing, (b) create a venv at `%LOCALAPPDATA%\Cubert GmbH\Cuvis.AI UI\server-venv\`, (c) `uv sync` against the shipped cuvis-ai-core source so torch CUDA 12.8 + cuvis SDK binding + cuvis-ai-schemas land in the venv, (d) install pystray for the tray icon, and (e) download FFmpeg LGPL + Graphviz portable into `{app}\ffmpeg\` and `{app}\graphviz\`. Build time drops from ~25 min to ~3 min. Removed `installer\cuvis_ai_core.spec` and `installer\fetch_vendor.ps1`; reverted the temporary plugin-venv detour in `cuvis_ai_core.utils.git_and_os` (server now runs in a real venv, so the original `uv pip install` works for plugin dep installs out of the box).
- Added a windowless tray app for the server. `installer\server-launcher.cmd` is the Start Menu target — it prepends `{app}\ffmpeg\bin` + `{app}\graphviz\bin` to PATH and runs the venv's `pythonw.exe` against `installer\server_launcher.py`, which redirects stdout/stderr to `server.log`, runs `serve()` on a daemon thread, and shows a `pystray` icon with **Open log…**, **Open data folder…**, and **Quit** menu items.
- Added a fast TCP probe in `cuvis_ai_ui/main.py` before `client.connect()`. If no process is listening on the configured host:port the UI surfaces the "Server Not Running" dialog within ~1 s instead of waiting through gRPC's 3-attempt retry.
- Changed the local gRPC server to a manual launch step. `connection.json` now defaults `auto_start` to `false`, the new "Server Not Running" dialog tells the user to launch the server first, and the Inno Setup installer adds a `Cuvis.AI Server` Start Menu shortcut next to `Cuvis.AI UI`. Users who want the legacy auto-start behavior can re-enable it via Tools → Connect to Server.
- Added a post-install dialog in `installer/cuvis_ai_ui.iss` that links to the Cubert SDK download page. The Cuvis C++ SDK is not bundled and must be installed separately for `.cu3s` / `.cu3` I/O.
- Changed `cuvis_ai_catalog.yaml` to fetch the cuvis-ai node catalog from `https://github.com/cubert-hyperspectral/cuvis-ai.git` at tag `v0.7.0` via `GitPluginConfig`, instead of pointing to a developer-machine absolute path. Provides list mirrors `cuvis-ai-docs-revision/configs/plugins/cuvis_ai_builtin.yaml`.
- Removed the dead `SCHEMAS_ROOT` `pathex` entry from both PyInstaller specs; `cuvis-ai-schemas` is now resolved by `collect_all` via site-packages whether the dep comes from PyPI or a local editable override.
- Changed UI to use new schema fields (`class_name`, `source`/`target`)
- Changed `plugin_manager.py` to import directly from `settings.plugins`
- Removed backward-compat `plugin_settings.py` re-export shim
- Fixed unused `qtbot` test fixture in pipeline info dialog tests
- Added drag-and-drop from the node palette onto the canvas: a `CanvasDropTarget` event filter on the NodeGraphQt viewer accepts `application/x-cuvis-node` MIME drags emitted by `NodePalette._start_drag`, maps the drop position into scene coordinates, and creates the node at that location.
- Added category-grouped node palette consuming `NodeInfo.category`, `tags`, and `icon_svg` from the proto. One section per `NodeCategory` in enum order with category-coloured backgrounds and embedded SVG icons; tag chips painted by a new `NodePaletteDelegate`.
- Added collapsible `TagFilterWidget` with one section per tag namespace (modality, task, lifecycle, properties, backend) — replaced shortly after by a unified autocomplete input.
- Changed the palette's tag filter and search bar into a single `QLineEdit` + `QCompleter` that suggests tag short-labels and full names; picks become removable chips. Filter semantic preserved (OR-within / AND-across tag namespaces) but invisible to the user. Per-row inline tag chips removed; tags remain visible in tooltips.
- Changed `node_adapter.py` to consume `category` / `tags` / `icon_svg` from `NodeInfo` via `proto_to_node_*` helpers; dropped path-based category inference and the `CATEGORY_COLORS` dict. Renamed `get_nodes_by_category` to `group_by_category(nodes)`; the old source-based lookup is now `get_nodes_by_source`.
- Refactored `node_adapter.configure_from_node_info`: extracted two near-identical 30-line port-spec parsing blocks into module-level `_parse_shape` and `_parse_port_spec` helpers. Typed the node-info dict via a `NodeInfoDict` `TypedDict`; `tags` and `category` stay as raw proto-wire ints so a forward-compat server cannot blow up the dict construction site.
- Fixed `_create_node` placeholder ports for unknown classes: the loader now pre-scans the connection list, derives input/output port names referenced for each unknown class, and creates those ports on the placeholder with `dtype="any"` so the graph topology survives the load. Previously every connection touching the placeholder was silently dropped. Placeholder classes are cached by class path so multiple instances share one registered NodeGraphQt class.
- Removed the local `cuvis-ai-schemas` editable path source; clean checkouts now resolve schemas `>=0.4.0` from PyPI.
- Fixed reconnect dropping the node palette. `cuvis_ai_ui/main.py` now exposes `reload_session_after_connect()` which replays the plugin manifest before calling `list_available_nodes`, so the new server's catalog repopulates after a Tools → Connect to Server reconnection (previously the palette went empty because the new server started fresh).
- Changed `requires-python` in `pyproject.toml` from `<3.12` to `<3.14`, so cuvis-ai-ui can be installed and developed on CPython 3.12 and 3.13 as well as 3.11.
- Bumped minimum versions of runtime / build dependencies: `PySide6 >=6.11.0`, `NodeGraphQt >=0.6.44`, `matplotlib >=3.10.8`, `loguru >=0.7.3`, `grpcio-tools >=1.80.0`, `setuptools-scm >=10.0.5`, `setuptools >=82.0.1`, `pip-licenses >=5.5.5`, `cyclonedx-bom >=7.3.0`, `bandit >=1.9.4`. Bumped CI actions: `softprops/action-gh-release v3`, `codecov/codecov-action v6`, `actions/download-artifact v8`.

## 0.1.0

- Added visual pipeline editor with drag-and-drop node connections
- Added node palette with search and categorized browsing
- Added property editor with dynamic parameter forms
- Added pipeline YAML load/save support
- Added plugin manager for extending available nodes
- Added gRPC client integration with cuvis-ai-core
- Added server connection dialog with local auto-start and remote support
- Added Windows installer bundling UI and gRPC server with PyTorch CUDA 12.8
- Added CI/CD workflows with GitHub Actions
- Added Codecov integration
