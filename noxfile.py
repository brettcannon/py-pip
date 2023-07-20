import pathlib
import shutil
import tomllib  # type: ignore
import zipapp

import nox  # type: ignore

WORKSPACE = pathlib.Path(__file__).parent
LOCK_FILE = WORKSPACE / "requirements.txt"


def min_python_version() -> str:
    """Calculate the minimum Python version that is supported."""
    with open(WORKSPACE / "pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    return pyproject["project"]["requires-python"].removeprefix(">=").strip()


MIN_PYTHON_VERSION = min_python_version()


def pip(session, args):
    session.run("py", "-m", "pip", *args, external=True)


def install_deps(session, target, editable=False):
    """Install from the lock file into 'target'.

    If editable is true, then install the source code as editable.
    """
    requirements_args = [
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
        LOCK_FILE,
    ]

    pip(session, requirements_args)

    install_code_args = ["install", "--no-deps", f"--target={target}"]
    if editable:
        install_code_args.append("-e")
    install_code_args.append(".")

    pip(session, install_code_args)

    for unneeded_dir in ("lib", "bin"):
        path = target / unneeded_dir
        if path.exists():
            shutil.rmtree(path)

    # Strip unnecessary Rich dependencies.
    projects = ["markdown_it", "mdurl", "pygments"]
    for project in projects:
        for path in target.iterdir():
            if path.name.lower().startswith(project):
                shutil.rmtree(path)


@nox.session(python=False)
def venv(session):
    """Create a virtual environment."""
    venv_path = WORKSPACE / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)
    session.run("py", f"-{MIN_PYTHON_VERSION}", "-m", "venv", venv_path, external=True)
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
        path.mkdir()

    install_deps(session, build_path)
    next(build_path.glob("bdist.*")).rmdir()
    # Keep the .dist-info directories for the licenses.
    # XDG places its license in the wrong place (and with a misspelling).
    (build_path / "LICENCE").rename(
        next(build_path.glob("xdg-*.dist-info")) / "LICENSE"
    )
    shutil.copy(WORKSPACE / "LICENSE", build_path)
    shutil.copy(WORKSPACE / "THIRD_PARTY_NOTICES.md", build_path)

    zipapp.create_archive(
        build_path, dist_path / "py-pip.pyz", interpreter="/usr/bin/env py"
    )


@nox.session(python=MIN_PYTHON_VERSION)
def lock(session):
    """Update the lock file (and recreate the virtual environment)."""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    session.install("pip-tools")
    # `--pip-args` doesn't work when specified in `[tool.pip-tools]`.
    session.run(
        "pip-compile",
        "--pip-args",
        "--only-binary :all:",
        "--config",
        WORKSPACE / "pyproject.toml",
        external=True,
        env={"CUSTOM_COMPILE_COMMAND": f"nox -s {session.name}"},
    )
    # Safety check plus going to need to update it anyway.
    venv(session)
