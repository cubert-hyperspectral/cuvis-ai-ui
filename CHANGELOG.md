# Changelog

## [Unreleased]

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
