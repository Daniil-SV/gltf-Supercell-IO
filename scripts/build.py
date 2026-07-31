import os
from utilities import zip_folder

DIRNAME = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(DIRNAME, "../", "gltf_supercell_io")
OUTPUT_FOLDER = os.path.join(DIRNAME, "../", "dist")
OUTPUT_NAME = os.path.join(OUTPUT_FOLDER, "gltf_supercell_io.zip")


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    zip_folder(INPUT_FOLDER, OUTPUT_NAME)
