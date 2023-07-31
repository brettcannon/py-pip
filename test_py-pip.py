import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

import pytest


@pytest.fixture(scope="session")
def download_cache(tmp_path_factory):
    """Create a directory to store `pip.pyz` and the response headers."""
    cache_dir = tmp_path_factory.mktemp("download-cache")
    response = urllib.request.urlopen("https://bootstrap.pypa.io/pip/pip.pyz")
    headers = dict(response.getheaders())
    (cache_dir / "response_headers.json").write_text(json.dumps(headers))
    (cache_dir / "pip.pyz").write_bytes(response.read())
    return cache_dir


@pytest.fixture
def py_pip_cache(download_cache, tmp_path):
    """Create an XDG cache directory and a `py-pip` subdirectory."""
    xdg_cache_dir = tmp_path / "xdg-cache-home"
    cache_dir = xdg_cache_dir / "py-pip"
    cache_dir.mkdir(parents=True)

    shutil.copytree(download_cache, cache_dir, dirs_exist_ok=True)

    os.environ["XDG_CACHE_HOME"] = os.fsdecode(xdg_cache_dir)
    try:
        yield cache_dir
    finally:
        del os.environ["XDG_CACHE_HOME"]


@pytest.fixture
def py_pip(py_pip_cache):
    """Run `py-pip.pyz`."""

    def runner(*args):
        executable = sys.executable
        pyz_path = pathlib.Path(__file__).parent / "dist" / "py-pip.pyz"
        return subprocess.run(
            [executable, pyz_path, *args], capture_output=True, check=True, text=True
        )

    return runner


def test_no_pyz():
    # XXX `pip.pyz` missing
    pass


def test_need_venv_no_pyproject():
    # XXX not in a virtual environment; no `pyproject.toml`
    pass


def test_need_venv_found_pyproject():
    # XXX not in a virtual environment; `pyproject.toml` found
    pass


def test_updating_pip():
    # XXX pip needs updating
    pass


def test_pip_runs(py_pip):
    """Output of `py-pip.pyz --version` should match `pip --version`."""
    proc = py_pip("--version")

    # There should be no output other than `pip --version`.
    assert re.match(r"pip \d+\.\d+\.\d+ from", proc.stdout)
    assert not proc.stderr
