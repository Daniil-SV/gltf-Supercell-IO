import os
from utilities import zip_folder

DIRNAME = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(DIRNAME, "../", "gltf_image_converter")
OUTPUT_FOLDER = os.path.join(DIRNAME, "../", "dist")
OUTPUT_NAME = os.path.join(OUTPUT_FOLDER, "gltf_image_converter.zip")


if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    zip_folder(INPUT_FOLDER, OUTPUT_NAME)
