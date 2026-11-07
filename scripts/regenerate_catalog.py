"""Mirror cuvis-ai's plugin manifests into the bundled catalog.

The UI ships every manifest cuvis-ai keeps under ``cuvis_ai/configs/plugins/``
as package data in ``cuvis_ai_ui/catalog/``. At startup each one is registered
with the server (``LoadPlugin``), and the server builds the node palette from the
manifests' ``capabilities`` without importing any plugin code.

The files are copied byte for byte from a cuvis-ai release tag of a local
cuvis-ai checkout, each one validated against the cuvis-ai-schemas manifest
model first. Only released plugins are bundled: a manifest with a local
``path:`` source (a developer checkout) is skipped, because a server that later
materialises that plugin would install whatever sits at that path on the user's
machine. Such plugins load from the app's plugins folder or ``--plugins-dir``.
Manifests that are gone upstream are deleted from the catalog. Run it for every
cuvis-ai release the UI should follow:

    uv run python scripts/regenerate_catalog.py --tag v0.22.6
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click
import yaml
from cuvis_ai_schemas.plugin import parse_plugin_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "cuvis_ai_ui" / "catalog"
# cuvis-ai sits beside cuvis-ai-ui under the same parent folder.
DEFAULT_CUVIS_AI = REPO_ROOT.parent.parent / "cuvis-ai" / "cuvis-ai"
MANIFEST_DIR = "cuvis_ai/configs/plugins"

README = """# Bundled plugin catalog

{count} released plugin {manifests} mirrored from cuvis-ai `{tag}` (`{manifest_dir}/`),
each pinned to a git repo and tag. The UI registers each one with the server at
startup; the node palette is built from their `capabilities`. Manifests with a
local `path:` source are not bundled; load those from the app's plugins folder or
with `--plugins-dir`.

Do not edit these files by hand. Regenerate them for a new cuvis-ai release:

    uv run python scripts/regenerate_catalog.py --tag <cuvis-ai tag>
"""


def _git(repo: Path, *args: str) -> bytes:
    """Run a git command in ``repo`` and return its stdout."""
    cmd = ["git", "-C", str(repo), *args]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else ""
        message = f"{' '.join(cmd)} failed"
        if stderr:
            message = f"{message}: {stderr}"
        raise click.ClickException(message) from exc
    return result.stdout


def list_manifests(repo: Path, tag: str, manifest_dir: str) -> list[str]:
    """Return the manifest file names in ``manifest_dir`` at ``tag``."""
    output = _git(repo, "ls-tree", "-z", "--name-only", f"{tag}:{manifest_dir}")
    names = output.decode().split("\0")[:-1]
    return sorted(n for n in names if n.endswith((".yaml", ".yml")))


def mirror(repo: Path, tag: str, manifest_dir: str, catalog: Path) -> tuple[list[str], list[str]]:
    """Copy and validate the released manifests at ``tag``.

    Returns the mirrored file names and the skipped ``path:``-sourced ones.
    Catalog files that are not mirrored this time are deleted.
    """
    names = list_manifests(repo, tag, manifest_dir)
    if not names:
        raise click.ClickException(f"No manifests in {manifest_dir} at {tag}")

    blobs: dict[str, bytes] = {}
    skipped: list[str] = []
    for name in names:
        blob = _git(repo, "show", f"{tag}:{manifest_dir}/{name}")
        try:
            manifest = parse_plugin_manifest(yaml.safe_load(blob.decode("utf-8")))
        except Exception as exc:
            raise click.ClickException(f"{name} at {tag} is not a valid manifest: {exc}") from exc
        if getattr(manifest, "repo", None):
            blobs[name] = blob
        else:
            skipped.append(name)

    catalog.mkdir(parents=True, exist_ok=True)
    for stale in [*catalog.glob("*.yaml"), *catalog.glob("*.yml")]:
        if stale.name not in blobs:
            stale.unlink()
    for name, blob in blobs.items():
        (catalog / name).write_bytes(blob)
    readme = README.format(
        count=len(blobs),
        manifests="manifest" if len(blobs) == 1 else "manifests",
        tag=tag,
        manifest_dir=manifest_dir,
    )
    (catalog / "README.md").write_text(readme, encoding="utf-8")
    return sorted(blobs), skipped


@click.command()
@click.option("--tag", required=True, help="cuvis-ai release tag to mirror, e.g. v0.22.6.")
@click.option(
    "--cuvis-ai",
    "cuvis_ai_repo",
    type=click.Path(path_type=Path, file_okay=False),
    default=DEFAULT_CUVIS_AI,
    show_default=True,
    help="Local cuvis-ai checkout that has the tag.",
)
@click.option(
    "--manifest-dir",
    default=MANIFEST_DIR,
    show_default=True,
    help="Folder of plugin manifests inside cuvis-ai.",
)
@click.option(
    "--catalog",
    type=click.Path(path_type=Path, file_okay=False),
    default=DEFAULT_CATALOG,
    show_default=True,
    help="Bundled catalog folder to write.",
)
def main(tag: str, cuvis_ai_repo: Path, manifest_dir: str, catalog: Path) -> None:
    """Mirror cuvis-ai's plugin manifests at TAG into the bundled catalog."""
    names, skipped = mirror(cuvis_ai_repo, tag, manifest_dir, catalog)
    click.echo(f"Mirrored {len(names)} manifests from cuvis-ai {tag} into {catalog}")
    if skipped:
        click.echo(f"Skipped {len(skipped)} with a local path source: {', '.join(skipped)}")


if __name__ == "__main__":
    main()
