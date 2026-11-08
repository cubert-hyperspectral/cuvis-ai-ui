"""CLI entry point for cuvis-ai-ui.

``cuvis-ui [PATH]`` launches the Qt application (NodeGraphQt canvas, node
palette, property editor) connected to a cuvis-ai-core server. PATH is a
pipeline YAML file or a folder of pipelines.
"""

import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

import click
from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .grpc.client import CuvisAIClient
from .main_window import MainWindow
from .server import ServerManager, is_listening
from .settings import (
    collect_plugin_entries,
    get_plugin_store_path,
    load_connection_settings,
    set_app_identity,
)
from .widgets import NodePalette, PluginManagerDialog, PropertyEditor
from .widgets.blocking_task import (
    SERVER_WAIT_CANCELLED,
    TaskStatus,
    run_blocking,
    wait_for_server,
)
from .workspace import plugin_dirs_for, register_plugins, resolve_launch_target


def _start_local_server(port: int) -> tuple[ServerManager, bool]:
    """Start the local server and wait for it behind a dialog with Cancel.

    Returns the manager and whether the user cancelled the wait; the server
    keeps starting after a cancel.
    """
    manager = ServerManager(port=port)
    manager.start()
    if manager.process is None:
        QMessageBox.warning(None, "Server Not Started", manager.last_error)
        return manager, False

    waited = wait_for_server(manager, None)
    if waited.status is TaskStatus.CANCELLED:
        logger.info("Stopped waiting for the local server; it keeps starting.")
        return manager, True
    if not waited.value:
        output = waited.error or manager.last_error
        detail = f"\n\nServer output:\n{output}" if output else ""
        QMessageBox.warning(
            None,
            "Server Start Warning",
            "The local gRPC server did not become ready in time.\n\n"
            "You can still view and edit pipelines, but the node catalog needs "
            f"the server. Its log is {manager.log_path}.{detail}",
        )
    return manager, False


def _connect(host: str, port: int) -> CuvisAIClient | None:
    """Connect to the server, or explain why not and return None."""
    if not is_listening(host, port):
        logger.warning(f"No server listening on {host}:{port}; skipping connect.")
        QMessageBox.warning(
            None,
            "Server Not Running",
            f"No cuvis-ai-core server is listening on {host}:{port}.\n\n"
            "Start it from the start menu (Cuvis.AI UI > Cuvis.AI Server), or "
            "launch the UI with --start-server. Then use Tools > Connect to "
            "Server to retry.\n\n"
            "You can still view and edit pipelines without a server, but "
            "the node catalog, inference, and training all require it.",
        )
        return None
    client = CuvisAIClient(host=host, port=port)
    connected = run_blocking(
        None,
        "Connecting",
        f"Connecting to the cuvis-ai-core server at {host}:{port}...",
        lambda stop: client.connect(stop=stop),
    )
    if connected.status is TaskStatus.CANCELLED:
        logger.info(f"Connecting to {host}:{port} cancelled.")
        return None
    if connected.status is TaskStatus.FAILED:
        logger.warning(f"Failed to connect to gRPC server: {connected.error}")
        QMessageBox.warning(
            None,
            "Connection Failed",
            f"A process is listening on {host}:{port} but the gRPC handshake "
            f"failed:\n{connected.error}\n\n"
            "If you just started the server, give it a few seconds for "
            "torch + CUDA to finish loading, then use Tools > Connect to "
            "Server to retry.",
        )
        return None
    logger.info(f"Connected to gRPC server at {host}:{port}, session: {client.session_id}")
    return client


@click.command()
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--plugins-dir",
    "plugins_dirs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Folder of plugin manifests to register (repeatable). A pipelines "
    "folder's own plugins/ subfolder is added without this option.",
)
@click.option(
    "--start-server",
    is_flag=True,
    help="Start the local cuvis-ai-core server for this run if none is listening.",
)
@click.option(
    "--test",
    "run_test",
    is_flag=True,
    help="Run a gRPC connection test and exit instead of launching the GUI.",
)
def main(
    path: Path | None, plugins_dirs: Sequence[Path], start_server: bool, run_test: bool
) -> None:
    """Launch the Cuvis.AI UI.

    PATH is a pipeline YAML file or a folder of pipelines. A folder opens in
    the Pipelines dock with its first pipeline, and the manifests in its
    plugins/ subfolder are registered with the server. With --test it runs
    a connection test and exits without opening the GUI.
    """
    set_app_identity()
    folder, pipeline = resolve_launch_target(path)
    conn = load_connection_settings()
    host = "localhost" if conn["mode"] == "local" else conn["host"]
    port = conn["port"]

    if run_test:
        _run_connection_test(host, port, plugin_dirs_for(plugins_dirs, folder))
        return

    logger.info("Starting cuvis-ai-ui...")
    app = QApplication(sys.argv)

    icon_path = Path(__file__).parent / "resources" / "icons" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    server_manager: ServerManager | None = None
    wait_cancelled = False
    wants_server = start_server or conn.get("auto_start", False)
    if conn["mode"] == "local" and wants_server and not is_listening(host, port):
        server_manager, wait_cancelled = _start_local_server(port)

    # After the user's own cancel, no "Server Not Running" box: the status bar says why
    client = None if wait_cancelled else _connect(host, port)
    window = MainWindow(client=client)
    window.set_server_manager(server_manager)

    palette = NodePalette(node_registry=window.node_registry, graph=window.graph)
    window.set_palette_widget(palette)
    property_editor = PropertyEditor()
    window.set_properties_widget(property_editor)
    window.node_selected.connect(property_editor.set_node)

    def refresh_plugins(fresh_session: bool) -> None:
        """Register every plugin source with the server and refresh the palette.

        ``fresh_session`` replaces the server session first, so plugins from a
        previous folder or a removed manifest are gone.
        """
        current_client = window.client
        if current_client is None:
            window.set_known_plugins(None)
            return

        def drop_catalog() -> None:
            # The session may already be a fresh one holding part of the set or
            # nothing: offer no nodes or plugin names rather than stale ones.
            window.node_registry.clear()
            window.node_registry.register_with_graph(window.graph)
            palette.refresh_nodes([])
            window.set_known_plugins(set())

        def fail(error: str, exc: BaseException | None = None) -> None:
            # A plain traceback: loguru's diagnose mode would print variable
            # values, such as a manifest's repository URL with its token.
            trace = "\n" + "".join(traceback.format_exception(exc)) if exc else ""
            logger.error(f"Failed to register plugins: {error}{trace}")
            drop_catalog()
            QMessageBox.warning(
                window,
                "Plugin Load Error",
                f"Failed to register plugins:\n{error}\n\n"
                "If plugin settings are stale, delete the persisted file and "
                f"restart:\n{get_plugin_store_path()}",
            )

        dirs = plugin_dirs_for(plugins_dirs, window.current_folder)
        try:
            entries = collect_plugin_entries(dirs)
        except Exception as e:
            fail(str(e), e)
            return
        registered = run_blocking(
            window,
            "Registering plugins",
            "Registering the plugins with the server...",
            lambda stop: register_plugins(
                current_client, entries, fresh_session=fresh_session, stop=stop
            ),
        )
        if registered.status is TaskStatus.FAILED:
            fail(registered.error)
            return
        if registered.status is TaskStatus.CANCELLED:
            drop_catalog()
            # Posted, not shown now: a folder switch opens its first pipeline
            # right after this returns, and its "Opened:" message would replace
            # the note on why the palette is empty.
            QTimer.singleShot(
                0,
                lambda: window.statusBar().showMessage(
                    "Plugin registration cancelled. "
                    "Tools > Refresh Nodes registers the plugins again."
                ),
            )
            return
        registration = registered.value
        assert registration is not None

        window.node_registry.clear()
        window.node_registry.register_nodes(registration.nodes)
        window.node_registry.register_with_graph(window.graph)
        palette.refresh_nodes(registration.nodes)
        window.set_known_plugins(registration.loaded)
        # A failed plugin stays on the status bar until the next message
        timeout = 0 if registration.failed else 10000
        window.statusBar().showMessage(registration.status_text(), timeout)
        if not registration.nodes:
            QMessageBox.warning(
                window,
                "No Nodes Available",
                "The server lists no nodes.\n\n"
                "Check the plugins in Tools > Manage Plugins. If plugin settings "
                f"are stale, delete the persisted file and restart:\n{get_plugin_store_path()}",
            )

    palette.refresh_requested.connect(lambda: refresh_plugins(fresh_session=True))
    refresh_action = window.refresh_nodes_action
    refresh_action.triggered.disconnect()
    refresh_action.triggered.connect(lambda: refresh_plugins(fresh_session=True))
    # A new folder brings its own plugins/ subfolder; a new server starts empty
    window.folder_changed.connect(lambda _folder: refresh_plugins(fresh_session=True))
    window.connection_status_changed.connect(
        lambda connected: refresh_plugins(fresh_session=False) if connected else None
    )

    def show_plugin_manager() -> None:
        current_client = window.client
        if current_client is None:
            QMessageBox.warning(
                window, "Not Connected", "Please connect to the gRPC server to manage plugins."
            )
            return
        extra_dirs = plugin_dirs_for(plugins_dirs, window.current_folder)
        PluginManagerDialog(current_client, window, extra_dirs=extra_dirs).exec()
        # Loads, removals and enable flags all change the plugin set
        refresh_plugins(fresh_session=True)

    plugins_action = window.plugins_action
    if plugins_action is not None:
        plugins_action.triggered.disconnect()
        plugins_action.triggered.connect(show_plugin_manager)

    window.show()
    if folder is not None:
        window.open_folder(folder, pipeline)
    else:
        refresh_plugins(fresh_session=False)
        if pipeline is not None:
            window.open_pipeline(pipeline)
    if wait_cancelled:
        # Last, so opening a pipeline does not replace it
        window.statusBar().showMessage(SERVER_WAIT_CANCELLED)

    sys.exit(app.exec())


@click.command()
@click.option("--host", default="localhost", show_default=True, help="gRPC server host.")
@click.option("--port", default=50051, show_default=True, type=int, help="gRPC server port.")
@click.option(
    "--plugins-dir",
    "plugins_dirs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Folder of plugin manifests to register (repeatable).",
)
def test_connection(host: str, port: int, plugins_dirs: Sequence[Path]) -> None:
    """Test the gRPC connection without launching the GUI.

    Useful for debugging and CI/CD validation.
    """
    set_app_identity()
    _run_connection_test(host, port, list(plugins_dirs))


def _run_connection_test(
    host: str = "localhost", port: int = 50051, plugin_dirs: Sequence[Path] = ()
) -> None:
    """Connect to the gRPC server, register plugins, and list available nodes."""
    print("=" * 60)
    print("cuvis-ai-ui - Connection Test")
    print("=" * 60)
    print()

    try:
        with CuvisAIClient(host=host, port=port) as client:
            print(f"[OK] Connected to gRPC server at {host}:{port}")
            print(f"[OK] Session ID: {client.session_id}")

            registration = register_plugins(client, collect_plugin_entries(plugin_dirs))
            if registration.loaded:
                print(f"[OK] Loaded plugins: {', '.join(registration.loaded)}")
            if registration.failed:
                print(f"[WARN] Failed plugins: {', '.join(registration.failed)}")

            nodes = registration.nodes
            print(f"[OK] Found {len(nodes)} available nodes")
            if nodes:
                print()
                print("Available nodes:")
                for node in nodes:
                    inputs = len(node.get("input_specs", []))
                    outputs = len(node.get("output_specs", []))
                    print(
                        f"  - {node['class_name']} ({node['source']}) [{inputs} in, {outputs} out]"
                    )

            print()
            print("[OK] All connection tests passed!")

    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        print()
        print("Make sure cuvis-ai-core gRPC server is running:")
        print("  cd D:\\code-repos\\cuvis-ai-core")
        print("  uv run python -m cuvis_ai_core.grpc.production_server")
        return


if __name__ == "__main__":
    main()
