import os
import pathlib
import subprocess
import sys
from typing import List

import microvenv
import rich.prompt

# XXX Execute pip from the virtual environment.


def in_virtual_env() -> bool:
    return sys.prefix != sys.base_prefix


def executable() -> pathlib.Path:
    if in_virtual_env():
        return pathlib.Path(sys.executable)
    else:
        cwd = pathlib.Path.cwd()
        locations = [cwd, *cwd.parents]
        for path in locations:
            pyproject_toml = path / "pyproject.toml"
            if pyproject_toml.exists():
                break
        else:
            selected_location = rich.prompt.Prompt.ask(
                "Where would you like the virtual environment to go? (default is cwd)",
                default=cwd,
            )
            path = pathlib.Path(selected_location)
        microvenv.create(path / ".venv")
        return path / ".venv" / "bin" / "python"


def pip(pyz_path: str, args: List[str]) -> int:
    args.insert(0, "--disable-pip-version-check")
    return subprocess.run([executable(), pyz_path, *args], check=False).returncode
