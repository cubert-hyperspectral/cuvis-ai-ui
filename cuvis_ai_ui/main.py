"""CLI entry point for cuvis-ai-ui.

This module provides the main entry point for the cuvis-visualizer command.
Launches the Qt application with NodeGraphQt canvas.
"""

import socket
import sys
from pathlib import Path

import click
from loguru import logger
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .adapters import enrich_node_list
from .grpc.client import CuvisAIClient
from .main_window import MainWindow
from .server import ServerManager
from .settings import (
    build_manifest,
    get_plugin_store_path,
    load_connection_settings,
    load_plugin_entries,
    write_manifest_temp,
)
from .widgets import NodePalette, PluginManagerDialog, PropertyEditor


def _server_is_listening(host: str, port: int, timeout: float = 1.0) -> bool:
    """Fast TCP probe so we can skip the gRPC retry loop when no server is up."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@click.command()
@click.option(
    "--test",
    "run_test",
    is_flag=True,
    help="Run a gRPC connection test and exit instead of launching the GUI.",
)
def main(run_test: bool) -> None:
    """Launch the Cuvis.AI UI.

    Starts the Qt application (NodeGraphQt canvas, node palette, property
    editor) connected to cuvis-ai-core. With ``--test`` it runs a connection
    test and exits without opening the GUI.
    """
    if run_test:
        _run_connection_test()
        return

    logger.info("Starting cuvis-visualizer...")

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Cuvis.AI UI")
    app.setOrganizationName("Cubert GmbH")

    icon_path = Path(__file__).parent / "resources" / "icons" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Load connection settings
    conn = load_connection_settings()
    server_manager: ServerManager | None = None

    # Auto-start local server if configured (only in frozen/installed builds)
    auto_start = conn.get("auto_start", False) and getattr(sys, "frozen", False)
    if conn["mode"] == "local" and auto_start:
        server_manager = ServerManager(port=conn["port"])
        server_manager.start()
        if not server_manager.wait_ready(timeout=30):
            error_detail = server_manager.last_error
            detail_text = f"\n\nServer output:\n{error_detail}" if error_detail else ""
            QMessageBox.warning(
                None,
                "Server Start Warning",
                "The local gRPC server did not become ready in time.\n\n"
                "You can still view and edit pipelines, but cannot:\n"
                "- Load node catalog from server\n"
                "- Run inference or training\n\n"
                f"Check connection settings via Tools → Connect to Server.{detail_text}",
            )

    # Connect to gRPC server. Probe first so the GUI doesn't block on the
    # gRPC retry loop when no server is listening.
    host = "localhost" if conn["mode"] == "local" else conn["host"]
    port = conn["port"]
    client = None
    if not _server_is_listening(host, port):
        logger.warning(f"No server listening on {host}:{port}; skipping connect.")
        QMessageBox.warning(
            None,
            "Server Not Running",
            f"No cuvis-ai-core server is listening on {host}:{port}.\n\n"
            "Start the server first:\n"
            "  Start menu → Cuvis.AI UI → Cuvis.AI Server\n"
            "  (the tray icon shows when it is ready)\n\n"
            "Then restart Cuvis.AI UI, or open Tools → Connect to Server "
            "to retry.\n\n"
            "You can still view and edit pipelines without a server, but "
            "the node catalog, inference, and training all require it.",
        )
    else:
        try:
            client = CuvisAIClient(host=host, port=port)
            client.connect()
            logger.info(f"Connected to gRPC server at {host}:{port}, session: {client.session_id}")
        except Exception as e:
            logger.warning(f"Failed to connect to gRPC server: {e}")
            QMessageBox.warning(
                None,
                "Connection Failed",
                f"A process is listening on {host}:{port} but the gRPC handshake "
                f"failed:\n{e}\n\n"
                "If you just started the server, give it a few seconds for "
                "torch + CUDA to finish loading, then use Tools → Connect to "
                "Server to retry.",
            )
            client = None

    # Create main window
    window = MainWindow(client=client)
    window.set_server_manager(server_manager)

    # Try to load persisted plugins if connected
    if client is not None:
        try:
            plugin_entries = load_plugin_entries()
            manifest = build_manifest(plugin_entries, enabled_only=True)
            if manifest.get("plugins"):
                temp_path = write_manifest_temp(manifest)
                try:
                    result = client.load_plugins(temp_path)
                finally:
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass

                loaded = result.get("loaded_plugins", [])
                failed = result.get("failed_plugins", [])

                if loaded:
                    logger.info(f"Loaded plugins: {loaded}")
                if failed:
                    logger.warning(f"Failed to load some plugins: {failed}")
            else:
                logger.info("No enabled plugins configured for startup.")

            # Refresh node registry (enrich with port specs from class introspection)
            nodes = client.list_available_nodes()
            logger.info(f"Retrieved {len(nodes)} nodes from server")
            nodes = enrich_node_list(nodes)
            window.node_registry.register_nodes(nodes)
            # Register node classes with graph for creation
            window.node_registry.register_with_graph(window.graph)
            logger.info(f"Registered {len(nodes)} nodes with graph")

            if len(nodes) == 0:
                store_path = get_plugin_store_path()
                QMessageBox.warning(
                    window,
                    "No Nodes Available",
                    "No nodes were loaded from the server.\n\n"
                    "Please check that:\n"
                    "- The cuvis-ai-catalog plugin is properly configured\n"
                    "- The server has access to the cuvis-ai package\n\n"
                    "If plugin settings are stale, delete the persisted file\n"
                    f"and restart:\n{store_path}\n\n"
                    "You can also reload plugins via Tools → Plugin Manager.",
                )
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}", exc_info=True)
            store_path = get_plugin_store_path()
            QMessageBox.warning(
                window,
                "Plugin Load Error",
                f"Failed to load plugins:\n{e}\n\n"
                "If plugin settings are stale, delete the persisted file\n"
                f"and restart:\n{store_path}\n\n"
                "You can also try again via Tools → Plugin Manager.",
            )

    # Create and attach widgets
    palette = NodePalette(
        node_registry=window.node_registry,
        graph=window.graph,
    )
    window.set_palette_widget(palette)

    # Refresh palette with loaded nodes
    if client is not None and window.node_registry.get_all_nodes():
        try:
            palette.refresh_nodes(window.node_registry.get_all_nodes())
            logger.info(f"Palette refreshed with {len(window.node_registry.get_all_nodes())} nodes")
        except Exception as e:
            logger.error(f"Failed to refresh palette: {e}")

    property_editor = PropertyEditor()
    window.set_properties_widget(property_editor)

    # Connect signals
    window.node_selected.connect(property_editor.set_node)

    # Handle palette refresh
    def on_refresh_requested() -> None:
        current_client = window.client
        if current_client is None:
            return
        try:
            nodes = current_client.list_available_nodes()
            nodes = enrich_node_list(nodes)
            palette.refresh_nodes(nodes)
            window.node_registry.register_nodes(nodes)
            window.node_registry.register_with_graph(window.graph)
        except Exception as e:
            logger.error(f"Failed to refresh nodes: {e}")
            QMessageBox.warning(window, "Refresh Failed", f"Failed to refresh node list:\n{e}")

    palette.refresh_requested.connect(on_refresh_requested)

    def reload_session_after_connect() -> None:
        """Re-prime a freshly connected server: load persisted plugins, then refresh nodes.

        On reconnect the new server is empty, so list_available_nodes alone
        would yield nothing — we must replay the same manifest-load that
        startup does before listing.
        """
        c = window.client
        if c is None:
            return
        try:
            plugin_entries = load_plugin_entries()
            manifest = build_manifest(plugin_entries, enabled_only=True)
            if manifest.get("plugins"):
                temp_path = write_manifest_temp(manifest)
                try:
                    result = c.load_plugins(temp_path)
                finally:
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                loaded = result.get("loaded_plugins", [])
                failed = result.get("failed_plugins", [])
                if loaded:
                    logger.info(f"Loaded plugins after reconnect: {loaded}")
                if failed:
                    logger.warning(f"Failed to load some plugins after reconnect: {failed}")

            nodes = c.list_available_nodes()
            nodes = enrich_node_list(nodes)
            logger.info(f"Retrieved {len(nodes)} nodes after reconnect")
            window.node_registry.clear()
            window.node_registry.register_nodes(nodes)
            window.node_registry.register_with_graph(window.graph)
            palette.refresh_nodes(nodes)
        except Exception as e:
            logger.error(f"Failed to bootstrap session after reconnect: {e}", exc_info=True)
            QMessageBox.warning(
                window,
                "Refresh Failed",
                f"Connected, but failed to reload plugins/nodes:\n{e}",
            )

    window.connection_status_changed.connect(
        lambda connected: reload_session_after_connect() if connected else None
    )

    # Override plugin manager action
    def show_plugin_manager() -> None:
        current_client = window.client
        if current_client is None:
            QMessageBox.warning(
                window, "Not Connected", "Please connect to the gRPC server to manage plugins."
            )
            return

        dialog = PluginManagerDialog(current_client, window)
        dialog.plugins_loaded.connect(lambda _: on_refresh_requested())
        dialog.exec()

    # Find and connect the plugin manager action
    plugins_action = getattr(window, "plugins_action", None)
    if plugins_action is not None:
        try:
            plugins_action.triggered.disconnect()
        except Exception:
            pass
        plugins_action.triggered.connect(show_plugin_manager)

    # Show window
    window.show()

    # Run application
    sys.exit(app.exec())


@click.command()
@click.option("--host", default="localhost", show_default=True, help="gRPC server host.")
@click.option("--port", default=50051, show_default=True, type=int, help="gRPC server port.")
def test_connection(host: str, port: int) -> None:
    """Test the gRPC connection without launching the GUI.

    Useful for debugging and CI/CD validation.
    """
    _run_connection_test(host, port)


def _run_connection_test(host: str = "localhost", port: int = 50051) -> None:
    """Connect to the gRPC server, load plugins, and list available nodes."""
    print("=" * 60)
    print("cuvis-ai-ui - Connection Test")
    print("=" * 60)
    print()

    try:
        from .grpc.client import CuvisAIClient

        with CuvisAIClient(host=host, port=port) as client:
            print(f"[OK] Connected to gRPC server at {host}:{port}")
            print(f"[OK] Session ID: {client.session_id}")

            # Load persisted / default plugins
            plugin_entries = load_plugin_entries()
            manifest = build_manifest(plugin_entries, enabled_only=True)
            if manifest.get("plugins"):
                print()
                print("Loading plugins...")
                temp_path = write_manifest_temp(manifest)
                try:
                    result = client.load_plugins(temp_path)
                    if result["loaded_plugins"]:
                        print(f"[OK] Loaded plugins: {', '.join(result['loaded_plugins'])}")
                    if result["failed_plugins"]:
                        print(f"[WARN] Failed plugins: {', '.join(result['failed_plugins'])}")
                except Exception as e:
                    print(f"[WARN] Plugin loading failed: {e}")
                finally:
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                print()

            nodes = client.list_available_nodes()
            nodes = enrich_node_list(nodes)
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
