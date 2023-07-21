import pathlib
import sys

import rich.console
import xdg

from . import download
from . import run


def select_dir() -> pathlib.Path:
    cwd = pathlib.Path.cwd()
    locations = [cwd, *cwd.parents]
    for path in locations:
        pyproject_toml = path / "pyproject.toml"
        if pyproject_toml.exists():
            break
    else:
        print("No pyproject.toml found.")
        print("Where do you want to save the virtual environment?")
        for option, path in enumerate(locations, start=1):
            print(f"{option}. {path}")
        selected_location = int(
            rich.prompt.IntPrompt.ask(
                "Select a location",
                choices=list(map(str, range(1, len(locations) + 1))),
                default="1",
            )
        )
        path = pathlib.Path(locations[selected_location - 1])
    return path


def main():
    pyz_path = download.pyz_path()
    pyz_bytes = download.download_pyz()
    if not pyz_bytes:
        print("Reusing", pyz_path)
    else:
        download.save_pyz(pyz_path, pyz_bytes)
        run.pip(sys.executable, pyz_path, args=["--version"])

    if run.in_virtual_env():
        py_path = pathlib.Path(sys.executable)
    else:
        workspace_path = select_dir()
        print("Creating virtual environment in", workspace_path)
        py_path = run.create_venv(workspace_path)

    console = rich.console.Console()
    console.rule("pip output")

    sys.exit(run.pip(py_path, pyz_path, args=sys.argv[1:]))


if __name__ == "__main__":
    main()
