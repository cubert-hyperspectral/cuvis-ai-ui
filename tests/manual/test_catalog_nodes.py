"""Test script to load and list cuvis-ai catalog nodes via gRPC.

This script demonstrates how to:
1. Connect to the gRPC server
2. Load every manifest in the bundled catalog folder via the LoadPlugin RPC
3. List all available nodes from the server
"""

from cuvis_ai_ui.grpc.client import CuvisAIClient
from cuvis_ai_ui.settings.plugins import get_catalog_dir


def main():
    print("=" * 60)
    print("Cuvis.AI Catalog Node Loading (via gRPC)")
    print("=" * 60)

    catalog_dir = get_catalog_dir()
    manifest_paths = sorted(catalog_dir.glob("*.yaml")) + sorted(catalog_dir.glob("*.yml"))
    if not manifest_paths:
        print(f"\n✗ No manifests found in: {catalog_dir}")
        return

    # Connect to server
    print("\n1. Connecting to cuvis-ai-core gRPC server...")
    try:
        with CuvisAIClient() as client:
            print(f"   ✓ Connected (session: {client.session_id})")

            # Load plugins from every manifest in the catalog
            print(f"\n2. Loading {len(manifest_paths)} catalog manifest(s) via LoadPlugin RPC...")
            try:
                for manifest_path in manifest_paths:
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
                print(f"\n   Note: Make sure the manifests in {catalog_dir} are correct")
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
    print("   Nodes are loaded via gRPC LoadPlugin RPC")
    print("   The server manages node registration per session")
    print("   Visualization client communicates purely via gRPC")
    print("=" * 60)


if __name__ == "__main__":
    main()
