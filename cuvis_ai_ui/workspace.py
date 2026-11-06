"""Pipeline folders and the plugin set the UI registers with the server."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from .adapters import enrich_node_list
from .grpc.client import CuvisAIClient
from .settings import build_manifest, write_manifest_temp

PLUGINS_SUBDIR = "plugins"
_PIPELINE_SUFFIXES = {".yaml", ".yml"}


def list_pipelines(folder: str | Path) -> list[Path]:
    """Return the pipeline YAML files directly inside ``folder``, sorted by name."""
    files = (
        p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in _PIPELINE_SUFFIXES
    )
    return sorted(files, key=lambda p: p.name.lower())


def resolve_launch_target(path: str | Path | None) -> tuple[Path | None, Path | None]:
    """Split the ``cuvis-ui PATH`` argument into ``(folder, pipeline)``.

    A folder opens in the pipelines browser with its first pipeline; a file
    opens on its own.
    """
    if path is None:
        return None, None
    target = Path(path)
    if target.is_dir():
        pipelines = list_pipelines(target)
        return target, pipelines[0] if pipelines else None
    if target.is_file():
        return None, target
    raise FileNotFoundError(target)


def plugin_dirs_for(cli_dirs: Iterable[str | Path], folder: str | Path | None) -> list[Path]:
    """Plugin folders for this run: each ``--plugins-dir``, then ``<folder>/plugins``."""
    dirs = [Path(d) for d in cli_dirs]
    if folder is not None and (Path(folder) / PLUGINS_SUBDIR).is_dir():
        dirs.append(Path(folder) / PLUGINS_SUBDIR)
    return dirs


@dataclass
class PluginRegistration:
    """What the server accepted from one plugin registration."""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    loaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def status_text(self) -> str:
        """One line for the status bar, naming every plugin that failed."""

        def count(n: int, noun: str) -> str:
            return f"{n} {noun}" if n == 1 else f"{n} {noun}s"

        text = f"{count(len(self.loaded), 'plugin')}, {count(len(self.nodes), 'node')}"
        if self.failed:
            text += "; failed to load: " + ", ".join(self.failed)
        return text


def register_plugins(
    client: CuvisAIClient,
    entries: list[dict[str, Any]],
    *,
    fresh_session: bool = False,
) -> PluginRegistration:
    """Register the enabled plugin entries with the server and list its nodes.

    The server only adds plugins to a session, so a changed plugin set needs
    ``fresh_session=True``: the session is closed and a new one created before
    the full set is registered again. Registration is metadata only; the
    server clones, installs and imports a plugin when a pipeline that uses it
    is loaded for a run, so anything that runs pipelines must treat folder
    manifests as untrusted.
    """
    if fresh_session:
        client.close_session()
        client.create_session()

    result = PluginRegistration()
    manifest = build_manifest(entries, enabled_only=True)
    if manifest:
        temp_path = write_manifest_temp(manifest)
        try:
            response = client.load_plugins(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
        result.loaded = list(response.get("loaded_plugins", []))
        result.failed = list(response.get("failed_plugins", []))
        if result.failed:
            logger.warning(f"Failed to load plugins: {result.failed}")

    result.nodes = enrich_node_list(client.list_available_nodes())
    logger.info(f"Registered {result.status_text()}")
    return result
