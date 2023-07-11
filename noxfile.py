import os.path
import pathlib
import shutil
import tomllib

import nox  # type: ignore

WORKSPACE = pathlib.Path(__file__).parent


def min_python_version() -> str:
    with open(WORKSPACE / "pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    return pyproject["project"]["requires-python"].removeprefix(">=").strip()


def install_deps(session, target, min_version=None, editable=False):
    if not min_version:
        min_version = min_python_version()

    pip_args = [
        "install",
        f"--target={target}",
        "--implementation=py",
        f"--python-version={min_version}",
        "--abi=none",
        "--platform=any",
        "--only-binary=:all:",
    ]
    if editable:
        pip_args.append("-e")
    else:
        pip_args.append("--no-compile")
    pip_args.append(".")

    session.run("py", "-m", "pip", *pip_args)


@nox.session(python=False)
def venv(session):
    """Create a virtual environment."""
    venv_path = WORKSPACE / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)
    min_version = min_python_version()
    session.run("py", f"-{min_version}", "-m", "venv", venv_path)
    site_packages = venv_path / "lib" / f"python{min_version}" / "site-packages"
    install_deps(session, site_packages, min_version=min_version, editable=True)


@nox.session(python=False)
def build(session):
    """Build `py-pip.pyz`."""
    build_path = WORKSPACE / "build"
    dist_path = WORKSPACE / "dist"
    for path in (build_path, dist_path):
        if path.exists():
            shutil.rmtree(path)
    install_deps(session, build_path)
    shutil.rmtree(build_path / "bin")
    shutil.rmtree(build_path / "lib")
    shutil.copy(WORKSPACE / "THIRD_PARTY_NOTICES.md", build_path)

    shutil.make_archive(dist_path / "py-pip", "zip", build_path)
