import os
import pathlib
import subprocess
import sys
from typing import List

import microvenv
import rich.prompt


def in_virtual_env() -> bool:
    return sys.prefix != sys.base_prefix


def create_venv() -> pathlib.Path:
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
    microvenv.create(path / ".venv")
    return path / ".venv" / "bin" / "python"


def pip(py_path: pathlib.Path, pyz_path: pathlib.Path, args: List[str]) -> int:
    args.insert(0, "--disable-pip-version-check")
    return subprocess.run(
        [os.fsdecode(py_path), os.fsdecode(pyz_path), *args], check=False
    ).returncode
