import re
import sys
from pathlib import Path

import tomlkit

from .common import (
    base_folder,
    execute,
    execute_output,
)


def get_version() -> str:
    if len(sys.argv) != 2:
        print("Usage: uv run python -m scripts.release <version>")
        print("Example: uv run python -m scripts.release 1.1.3")
        raise SystemExit(1)

    version = sys.argv[1]

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        raise SystemExit(f"Invalid version: {version}")

    return version


def update_version(path: Path, target: str, version: str) -> None:
    print(f"Updating {path} -> {version}")

    document = tomlkit.parse(path.read_text(encoding="utf-8"))

    def set(obj, path, value):
        *path, last = path.split(".")
        for bit in path:
            obj = obj.setdefault(bit, {})
        obj[last] = value

    set(document, target, version)

    path.write_text(
        tomlkit.dumps(document),
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    version = get_version()
    tag = f"v{version}"

    # Make sure we're not accidentally releasing over an existing tag.\
    status, result = execute_output(("git", "tag", "--list", tag))
    if status != 0:
        raise SystemError("Failed to get git tags")

    if result.strip():
        raise SystemExit(f"Git tag already exists: {tag}")

    # Update pyproject
    pyproject = base_folder() / "pyproject.toml"
    plugin_manifest = base_folder() / "gltf_supercell_io/blender_manifest.toml"
    files = [pyproject, plugin_manifest]

    update_version(pyproject, "project.version", version)
    update_version(plugin_manifest, "version", version)

    # Show what we're about to commit
    execute(
        ("git", "diff", "--", *(str(path.relative_to(base_folder())) for path in files))
    )

    answer = input(f"\nCreate release {tag}? [y/N] ")

    if answer.lower() != "y":
        print("Aborted.")
        return

    # Commit
    execute(("git", "add", *(str(path.relative_to(base_folder())) for path in files)))

    execute(
        (
            "git",
            "commit",
            "-m",
            f"release: {tag}",
        )
    )

    # Tag the release commit
    execute(
        (
            "git",
            "tag",
            "-a",
            tag,
            "-m",
            f"Release {tag}",
        )
    )

    # Push commit and tag
    execute(("git", "push"))
    execute(("git", "push", "origin", tag))

    print(f"\nReleased {tag}")


if __name__ == "__main__":
    raise SystemExit(main())
