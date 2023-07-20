import os
import pathlib
import subprocess
import sys
from typing import List

import microvenv
import rich.prompt


def in_virtual_env() -> bool:
    return sys.prefix != sys.base_prefix


def create_venv(path: pathlib.Path) -> pathlib.Path:
    microvenv.create(path / ".venv")
    return path / ".venv" / "bin" / "python"


def pip(py_path: pathlib.Path, pyz_path: pathlib.Path, args: List[str]) -> int:
    args = ["--disable-pip-version-check", "--require-virtualenv", *args]
    return subprocess.run(
        [os.fsdecode(py_path), os.fsdecode(pyz_path), *args], check=False
    ).returncode
