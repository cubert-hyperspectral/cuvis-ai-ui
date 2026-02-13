"""PyInstaller entry point for the cuvis-ai-core gRPC server."""

from cuvis_ai_core.grpc.production_server import serve

if __name__ == "__main__":
    serve()
