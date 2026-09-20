from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

GITHUB_REPOSITORY_RE = re.compile(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 without loading the whole archive into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def find_manifest() -> Path:
    """Find the Blender extension manifest in the repository."""
    candidates = list(Path(".").rglob("blender_manifest.toml"))

    if not candidates:
        raise FileNotFoundError("Could not find blender_manifest.toml")

    if len(candidates) > 1:
        paths = "\n".join(f"  - {path}" for path in candidates)

        raise RuntimeError(
            "Found multiple blender_manifest.toml files. "
            "Pass --manifest explicitly:\n"
            f"{paths}"
        )

    return candidates[0]


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def get_github_repository(website: str) -> tuple[str, str]:
    match = GITHUB_REPOSITORY_RE.search(website)

    if not match:
        raise ValueError(
            "Could not determine GitHub repository from website URL:\n"
            f"  {website}\n"
            "Expected something like:\n"
            "  https://github.com/owner/repository"
        )

    return match.group(1), match.group(2)


def generate_index_json(
    *,
    version: str,
    zip_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> Path:
    """Generate Blender extension repository index.json."""

    if version.startswith("v"):
        raise ValueError(f"Version must not contain the 'v' prefix: {version!r}")

    if not zip_path.is_file():
        raise FileNotFoundError(f"Archive does not exist: {zip_path}")

    manifest = load_manifest(manifest_path)

    addon_id = manifest["id"]
    name = manifest["name"]
    manifest_version = manifest["version"]
    tagline = manifest["tagline"]
    maintainer = manifest["maintainer"]
    addon_type = manifest.get("type", "add-on")
    website = manifest["website"]
    blender_min = manifest["blender_version_min"]
    license_list = manifest["license"]
    tags = manifest.get("tags", [])
    permissions = manifest.get("permissions", {})

    owner, repository = get_github_repository(website)

    archive_filename = zip_path.name

    expected_filename = f"{addon_id}_{version}.zip"

    if archive_filename != expected_filename:
        raise ValueError(
            "Unexpected archive filename:\n"
            f"  Actual:    {archive_filename}\n"
            f"  Expected:  {expected_filename}"
        )

    archive_url = (
        f"https://github.com/{owner}/{repository}"
        f"/releases/download/v{version}/{archive_filename}"
    )

    archive_size = zip_path.stat().st_size
    archive_hash = f"sha256:{sha256_file(zip_path)}"

    index_data: dict[str, Any] = {
        "version": "v1",
        "blocklist": [],
        "data": [
            {
                "schema_version": "1.0.0",
                "id": addon_id,
                "name": name,
                "tagline": tagline,
                "version": manifest_version,
                "type": addon_type,
                "maintainer": maintainer,
                "license": license_list,
                "blender_version_min": blender_min,
                "website": website,
                "permissions": permissions,
                "tags": tags,
                "python_versions": ["3"],
                "archive_url": archive_url,
                "archive_size": archive_size,
                "archive_hash": archive_hash,
            }
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(
            index_data,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Generated: {output_path}")
    print(f"  manifest:      {manifest_path}")
    print(f"  archive:       {zip_path}")
    print(f"  archive_url:   {archive_url}")
    print(f"  archive_size:  {archive_size}")
    print(f"  archive_hash:  {archive_hash}")

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Blender extension index.json."
    )

    parser.add_argument(
        "--version",
        required=True,
        help="Release version without the 'v' prefix, e.g. 1.1.2",
    )

    parser.add_argument(
        "--zip",
        dest="zip_path",
        type=Path,
        required=True,
        help="Path to the built extension ZIP.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("index.json"),
        help="Output index.json path.",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to blender_manifest.toml.",
    )

    args = parser.parse_args()

    try:
        manifest_path = args.manifest or find_manifest()

        generate_index_json(
            version=args.version,
            zip_path=args.zip_path,
            output_path=args.output,
            manifest_path=manifest_path,
        )

    except (FileNotFoundError, RuntimeError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
