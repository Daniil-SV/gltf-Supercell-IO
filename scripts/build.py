import os
import re
from os import scandir
from pathlib import Path

from .common import BuildException, base_folder, execute, wheels_folder, zip_folder

DIRNAME = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(DIRNAME, "../", "gltf_supercell_io")
OUTPUT_FOLDER = os.path.join(DIRNAME, "../", "dist")
OUTPUT_NAME = os.path.join(OUTPUT_FOLDER, "gltf_supercell_io.zip")


def replace_wheels(toml: str, wheels: list[str]) -> str:
    wheels_toml = "wheels = [\n" + "".join(f'  "{wheel}",\n' for wheel in wheels) + "]"

    pattern = r"(?m)^wheels\s*=\s*\[[\s\S]*?\]"

    if not re.search(pattern, toml):
        raise ValueError("Could not find 'wheels' property")

    return re.sub(pattern, wheels_toml, toml, count=1)


if __name__ == "__main__":
    # Creating list of required wheels for addon
    status = execute(
        (
            "uv",
            "export",
            "--no-dev",
            "--format",
            "requirements-txt",
            "--no-hashes",
            "-o",
            "requirements-wheels.txt",
        ),
        base_folder(),
    )
    if status != 0:
        raise BuildException("Failed to generate requirements list")

    # Downloading wheels to addon folder
    status = execute(
        (
            "python",
            "-m",
            "pip",
            "download",
            "-r",
            "requirements-wheels.txt",
            "--only-binary=:all:",
            "-d",
            wheels_folder().as_posix(),
        ),
        base_folder(),
    )

    # Updating an array of wheels in blender manifest
    paths: list[Path] = []
    for f in scandir(wheels_folder()):
        if not f.name.endswith(".whl"):
            continue

        paths.append(Path(f.path).relative_to(base_folder() / "gltf_supercell_io"))

    manifest = base_folder() / "gltf_supercell_io" / "blender_manifest.toml"
    with open(manifest, "r") as f:
        data = f.read()

    data = replace_wheels(data, [path.as_posix() for path in paths])

    with open(manifest, "w") as f:
        f.write(data)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    zip_folder(INPUT_FOLDER, OUTPUT_NAME)
