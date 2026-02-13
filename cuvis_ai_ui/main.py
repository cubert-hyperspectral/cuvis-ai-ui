"""CLI entry point for cuvis-ai-ui.

This module provides the main entry point for the cuvis-visualizer command.
Launches the Qt application with NodeGraphQt canvas.
"""

import sys
from pathlib import Path

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


def main() -> None:
    """Main entry point for cuvis-visualizer.

    Launches the Qt application with:
    - Main window with NodeGraphQt canvas
    - Node palette (left dock)
    - Property editor (right dock)
    - gRPC connection to cuvis-ai-core
    """
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
    auto_start = conn.get("auto_start", True) and getattr(sys, "frozen", False)
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
                f"Check connection settings via Tools → Connect to Server.{detail_text}"
            )

    # Connect to gRPC server
    host = "localhost" if conn["mode"] == "local" else conn["host"]
    port = conn["port"]
    client = None
    try:
        client = CuvisAIClient(host=host, port=port)
        client.connect()
        logger.info(f"Connected to gRPC server at {host}:{port}, session: {client.session_id}")
    except Exception as e:
        logger.warning(f"Failed to connect to gRPC server: {e}")
        QMessageBox.warning(
            None,
            "Connection Warning",
            f"Failed to connect to cuvis-ai-core gRPC server at {host}:{port}:\n{e}\n\n"
            "You can still view and edit pipelines, but cannot:\n"
            "- Load node catalog from server\n"
            "- Run inference or training\n\n"
            "Check connection settings via Tools → Connect to Server."
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
                    "You can also reload plugins via Tools → Plugin Manager."
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
                "You can also try again via Tools → Plugin Manager."
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
        if client is not None:
            try:
                nodes = client.list_available_nodes()
                nodes = enrich_node_list(nodes)
                palette.refresh_nodes(nodes)
                window.node_registry.register_nodes(nodes)
                window.node_registry.register_with_graph(window.graph)
            except Exception as e:
                logger.error(f"Failed to refresh nodes: {e}")
                QMessageBox.warning(
                    window, "Refresh Failed",
                    f"Failed to refresh node list:\n{e}"
                )

    palette.refresh_requested.connect(on_refresh_requested)

    # Override plugin manager action
    def show_plugin_manager() -> None:
        if client is None:
            QMessageBox.warning(
                window, "Not Connected",
                "Please connect to the gRPC server to manage plugins."
            )
            return

        dialog = PluginManagerDialog(client, window)
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


def test_connection() -> None:
    """Test gRPC connection without launching GUI.

    Useful for debugging and CI/CD validation.
    """
    print("=" * 60)
    print("cuvis-ai-ui - Connection Test")
    print("=" * 60)
    print()

    try:
        from .grpc.client import CuvisAIClient

        with CuvisAIClient() as client:
            print(f"[OK] Connected to gRPC server at localhost:50051")
            print(f"[OK] Session ID: {client.session_id}")

            # Load cuvis-ai catalog nodes via plugin manifest
            manifest_path = Path(__file__).parent.parent / "cuvis_ai_catalog.yaml"
            if manifest_path.exists():
                print()
                print("Loading cuvis-ai catalog nodes...")
                try:
                    result = client.load_plugins(manifest_path)
                    if result["loaded_plugins"]:
                        print(f"[OK] Loaded plugins: {', '.join(result['loaded_plugins'])}")
                    if result["failed_plugins"]:
                        print(f"[WARN] Failed plugins: {', '.join(result['failed_plugins'])}")
                except Exception as e:
                    print(f"[WARN] Plugin loading failed: {e}")
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
                    print(f"  - {node['class_name']} ({node['source']}) [{inputs} in, {outputs} out]")

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
    # Allow running test_connection with --test flag
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_connection()
    else:
        main()
