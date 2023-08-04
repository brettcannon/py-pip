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

    def runner(*args, executable=sys.executable):
        pyz_path = pathlib.Path(__file__).parent / "dist" / "py-pip.pyz"
        return subprocess.run(
            [executable, pyz_path, *args], capture_output=True, text=True
        )

    return runner


@pytest.fixture
def quick_pip_check(py_pip):
    """Quick check against `pip --version`."""

    def runner():
        proc = py_pip("--version")

        # There should be no output other than `pip --version`.
        assert re.search(r"^pip \d+\.\d+\.\d+ from", proc.stdout, flags=re.MULTILINE)
        assert not proc.stderr
        assert not proc.returncode

    return runner


def test_no_pyz(py_pip_cache, quick_pip_check):
    """`pip.pyz` should be downloaded if it's missing."""
    pyz_path = py_pip_cache / "pip.pyz"
    pyz_path.unlink()

    quick_pip_check()

    cache_contents = {path.name for path in py_pip_cache.iterdir()}
    assert len(cache_contents) == 2
    assert "pip.pyz" in cache_contents
    assert "response_headers.json" in cache_contents


def test_need_venv_no_pyproject(py_pip, tmp_path, monkeypatch):
    """If not running from a virtual environment and no `pyproject.toml`, fail."""
    # Confidence check.
    assert not any(".venv" in frozenset(path.iterdir()) for path in tmp_path.iterdir())
    monkeypatch.chdir(tmp_path)
    # Python >=3.10; `strict` argument.
    system_executable = os.path.realpath(sys.executable)
    proc = py_pip("--version", executable=system_executable)

    assert proc.returncode


def test_need_venv_found_pyproject(py_pip, tmp_path, monkeypatch):
    """If not running from a venv but `pyproject.toml` found, create venv."""
    # Confidence check.
    assert not (tmp_path / ".venv").exists()
    (tmp_path / "pyproject.toml").write_text("# Nothing to see.", encoding="utf-8")
    # Make sure we have to search parents to find `pyproject.toml`.
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    monkeypatch.chdir(subdir)

    system_executable = os.path.realpath(sys.executable)
    proc = py_pip("--version", executable=system_executable)

    assert not proc.returncode
    assert (tmp_path / ".venv").is_dir()


def test_updating_pip(py_pip_cache, quick_pip_check):
    """Download `pip.pyz` if the file is out of date."""
    header_path = py_pip_cache / "response_headers.json"
    original_headers = json.loads(header_path.read_text(encoding="utf-8"))
    bad_headers = original_headers.copy()
    bad_headers["etag"] = "bad"
    header_path.write_text(json.dumps(bad_headers), encoding="utf-8")

    quick_pip_check()

    new_headers = json.loads(header_path.read_text(encoding="utf-8"))
    assert new_headers["etag"] == original_headers["etag"]
    assert new_headers["last-modified"] == original_headers["last-modified"]


def test_pip_runs(quick_pip_check):
    """Output of `py-pip.pyz --version` should match `pip --version`."""
    quick_pip_check()
