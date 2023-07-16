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


MIN_PYTHON_VERSION = min_python_version()


def install_deps(session, target, editable=False):
    pip_args = [
        "install",
        f"--python-version={MIN_PYTHON_VERSION}",
        "--implementation=py",
        "--abi=none",
        "--platform=any",
        "--only-binary=:all:",
        "--no-compile",
        "--require-hashes",
        "--no-deps",
        f"--target={target}",
        f"-r",
        WORKSPACE / "requirements.txt",
    ]

    session.run("py", "-m", "pip", *pip_args)

    if editable:
        session.run("py", "-m", "pip", "install", "--no-deps", "-e", ".")


@nox.session(python=False)
def venv(session):
    """Create a virtual environment."""
    venv_path = WORKSPACE / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)
    session.run("py", f"-{MIN_PYTHON_VERSION}", "-m", "venv", venv_path)
    site_packages = venv_path / "lib" / f"python{MIN_PYTHON_VERSION}" / "site-packages"
    install_deps(session, site_packages, editable=True)


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
    shutil.copy(WORKSPACE / "THIRD_PARTY_NOTICES.md", build_path)

    shutil.make_archive(dist_path / "py-pip", "zip", build_path)


@nox.session(python=MIN_PYTHON_VERSION)
def lock(session):
    session.install("pip-tools")
    session.run("pip-compile", "--pip-args", "--only-binary :all:")
