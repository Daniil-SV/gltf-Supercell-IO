import os
import zipfile
from pathlib import Path
from fnmatch import fnmatch

DIRNAME = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(DIRNAME, "../", "gltf_supercell_io")
OUTPUT_FOLDER = os.path.join(DIRNAME, "../", "dist")
OUTPUT_NAME = os.path.join(OUTPUT_FOLDER, "gltf_supercell_io.zip")


def load_ignore_patterns(root: Path):
    ignore_file = root / ".distignore"
    patterns = []

    if not ignore_file.exists():
        return patterns

    with ignore_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)

    return patterns


def should_ignore(path: Path, root: Path, patterns):
    rel_path = path.relative_to(root)
    rel_posix = rel_path.as_posix()
    if rel_posix == ".distignore":
        return True

    for pattern in patterns:
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")

            if dir_name in rel_path.parts:
                return True

        if fnmatch(rel_posix, pattern):
            return True

        if fnmatch(path.name, pattern):
            return True

    return False


def zip_folder(source_dir: str, output_zip: str):
    root = Path(source_dir).resolve()
    root_name = root.name
    patterns = load_ignore_patterns(root)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file():
                if should_ignore(path, root, patterns):
                    continue

                archive_path = Path(root_name) / path.relative_to(root)
                zf.write(path, archive_path.as_posix())

    print(f"Archive created: {output_zip}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    zip_folder(INPUT_FOLDER, OUTPUT_NAME)
