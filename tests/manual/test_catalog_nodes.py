"""Test script to load and list cuvis-ai catalog nodes via gRPC.

This script demonstrates how to:
1. Connect to the gRPC server
2. Load cuvis-ai catalog nodes via the LoadPlugins RPC
3. List all available nodes from the server
"""

from pathlib import Path
from cuvis_ai_ui.grpc.client import CuvisAIClient


def main():
    print("=" * 60)
    print("Cuvis-AI Catalog Node Loading (via gRPC)")
    print("=" * 60)

    manifest_path = Path(__file__).parent / "cuvis_ai_catalog.yaml"
    if not manifest_path.exists():
        print(f"\n✗ Manifest file not found: {manifest_path}")
        print("  Please ensure cuvis_ai_catalog.yaml exists in the project root")
        return

    # Connect to server
    print("\n1. Connecting to cuvis-ai-core gRPC server...")
    try:
        with CuvisAIClient() as client:
            print(f"   ✓ Connected (session: {client.session_id})")

            # Load plugins from manifest
            print("\n2. Loading cuvis-ai catalog nodes via LoadPlugins RPC...")
            try:
                result = client.load_plugins(manifest_path)

                if result["loaded_plugins"]:
                    print(f"   ✓ Loaded {len(result['loaded_plugins'])} plugin(s):")
                    for plugin in result["loaded_plugins"]:
                        print(f"      - {plugin}")

                if result["failed_plugins"]:
                    print(f"\n   ✗ Failed to load {len(result['failed_plugins'])} plugin(s):")
                    for plugin in result["failed_plugins"]:
                        print(f"      - {plugin}")

            except Exception as e:
                print(f"   ✗ Failed to load plugins: {e}")
                print("\n   Note: Make sure the path in cuvis_ai_catalog.yaml is correct")
                return

            # List available nodes
            print("\n3. Listing available nodes from server...")
            nodes = client.list_available_nodes()
            print(f"   Found {len(nodes)} total nodes\n")

            # Group by source
            builtin = [n for n in nodes if n["source"] == "builtin"]
            plugin_nodes = [n for n in nodes if n["source"] == "plugin"]

            if builtin:
                print(f"   Built-in Nodes ({len(builtin)}):")
                for node in sorted(builtin, key=lambda n: n["class_name"])[:10]:
                    print(f"      - {node['class_name']}")
                if len(builtin) > 10:
                    print(f"      ... and {len(builtin) - 10} more")

            if plugin_nodes:
                print(f"\n   Plugin Nodes ({len(plugin_nodes)}):")
                for node in sorted(plugin_nodes, key=lambda n: n["class_name"])[:10]:
                    print(
                        f"      - {node['class_name']} (from {node.get('plugin_name', 'unknown')})"
                    )
                if len(plugin_nodes) > 10:
                    print(f"      ... and {len(plugin_nodes) - 10} more")

            if not nodes:
                print("   ⚠ No nodes available")
                print("   Check that the plugin manifest paths are correct")

    except ConnectionError as e:
        print(f"   ✗ Connection failed: {e}")
        print("\n   Make sure the server is running:")
        print("      cd D:/code-repos/cuvis-ai-core")
        print("      uv run python -m cuvis_ai_core.grpc.production_server")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback

        traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print("   Nodes are loaded via gRPC LoadPlugins RPC")
    print("   The server manages node registration per session")
    print("   Visualization client communicates purely via gRPC")
    print("=" * 60)


if __name__ == "__main__":
    main()
