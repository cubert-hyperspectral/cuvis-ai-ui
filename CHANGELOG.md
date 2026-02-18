# Changelog

## [Unreleased]

- Changed UI to use new schema fields (`class_name`, `source`/`target`)
- Changed `plugin_manager.py` to import directly from `settings.plugins`
- Removed backward-compat `plugin_settings.py` re-export shim
- Fixed unused `qtbot` test fixture in pipeline info dialog tests
- Reformatted CHANGELOG to concise single-list style
- Updated release workflow changelog extraction for new heading format

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
