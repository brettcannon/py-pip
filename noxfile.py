import os.path
import pathlib
import shutil
import tomllib

import nox  # type: ignore

WORKSPACE = pathlib.Path(__file__).parent


@nox.session(python=False)
def venv(session: nox.Session):
    """Create a virtual environment."""
    venv_path = WORKSPACE / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)
    with open(WORKSPACE / "pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    min_version = pyproject["project"]["requires-python"].removeprefix(">=").strip()
    session.run("py", f"-{min_version}", "-m", "venv", venv_path)
    site_packages = venv_path / "lib" / f"python{min_version}" / "site-packages"
    session.run(
        "py",
        "-m",
        "pip",
        "install",
        f"--target={site_packages}",
        "--implementation=py",
        f"--python-version={min_version}",
        "--abi=none",
        "--platform=any",
        "--only-binary=:all:",
        "-e",
        ".",
    )
