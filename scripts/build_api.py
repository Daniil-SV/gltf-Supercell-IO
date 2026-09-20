from os import remove, scandir, makedirs
from shutil import copy, rmtree

from .common import (
    BuildException,
    base_folder,
    ensure_openapi,
    ensure_uv,
    execute,
    install_openapi,
    wheels_folder,
)

if __name__ == "__main__":
    if not ensure_uv():
        raise BuildException("API build requires installed uv package manager")

    # Ensure that openapi client is installed and available
    if not ensure_openapi():
        install_openapi()

    neko_api_folder = base_folder() / "neko"
    dist_folder = neko_api_folder / "dist"
    config_path = base_folder() / "api_config.yml"

    # client dir should be empty
    if neko_api_folder.exists():
        rmtree(neko_api_folder)
        neko_api_folder.mkdir()

    # Generating client
    status = execute(
        (
            "uv",
            "tool",
            "run",
            "openapi-python-client",
            "generate",
            "--url",
            "http://api.sc-workshop.com/docs/json",
            "--overwrite",
            "--output-path",
            neko_api_folder.as_posix(),
            "--config",
            config_path.as_posix(),
        )
    )
    if status != 0:
        raise BuildException("Failed to generate client")

    # Migrate poetry to uv
    status = execute(("uvx", "migrate-to-uv"), neko_api_folder.as_posix())
    if status != 0:
        raise BuildException("Failed to migrate client")

    # Build wheel package
    status = execute(("uv", "build", "--wheel"), neko_api_folder.as_posix())
    if status != 0:
        raise BuildException("Failed to build client")

    # Remove .whl files target wheels folder
    makedirs(wheels_folder(), exist_ok=True)
    for f in scandir(wheels_folder()):
        if f.name.startswith("neko_web_api_client"):
            remove(f.path)

    # Now copy compiled whl file
    for f in scandir(dist_folder):
        if f.name.endswith(".whl"):
            copy(f.path, wheels_folder() / f.name)
