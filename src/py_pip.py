import json
import os
import pathlib
import subprocess
import sys
from typing import List, Optional

import httpx
import microvenv
import rich.console
import rich.progress
import rich.prompt
import xdg


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"
CACHE_DIR = xdg.xdg_cache_home() / "py-pip"
CACHED_PYZ = CACHE_DIR / "pip.pyz"


def blocking_download() -> None:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers_cache = CACHE_DIR / "response_headers.json"
    # headers = {}
    # if headers_cache.exists():
    #     last_headers = json.loads(headers_cache.read_text(encoding="utf-8"))
    #     try:
    #         # https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests
    #         headers["If-Modified-Since"] = last_headers["last-modified"]
    #         headers["If-None-Match"] = last_headers["etag"]
    #     except KeyError:
    #         pass

    with httpx.stream(http_verb, PYZ_URL) as response:
        # XXX handle errors

        headers_cache.parent.mkdir(parents=True, exist_ok=True)
        headers_cache.write_text(json.dumps(dict(response.headers)), encoding="utf-8")

        content = []
        total = int(response.headers["Content-Length"])

        with rich.progress.Progress(
            "[progress.percentage]{task.percentage:>3.0f}%",
            rich.progress.BarColumn(bar_width=None),
            rich.progress.DownloadColumn(),
            rich.progress.TransferSpeedColumn(),
        ) as progress:
            download_task = progress.add_task(f"Download", total=total)
            for chunk in response.iter_bytes():
                content.append(chunk)
                progress.update(download_task, completed=response.num_bytes_downloaded)

    CACHED_PYZ.write_bytes(b"".join(content))


def background_download() -> bool:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers_cache = CACHE_DIR / "response_headers.json"
    headers = {}
    if headers_cache.exists():
        last_headers = json.loads(headers_cache.read_text(encoding="utf-8"))
        try:
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests
            headers["If-Modified-Since"] = last_headers["last-modified"]
            headers["If-None-Match"] = last_headers["etag"]
        except KeyError:
            pass

    with httpx.stream(http_verb, PYZ_URL, headers=headers) as response:
        # XXX handle errors

        if response.status_code == 304:
            print("No new pip version available.")
            return False

        headers_cache.write_text(json.dumps(dict(response.headers)), encoding="utf-8")

        content = []
        total = int(response.headers["Content-Length"])

        with rich.progress.Progress(
            "[progress.percentage]{task.percentage:>3.0f}%",
            rich.progress.BarColumn(bar_width=None),
            rich.progress.DownloadColumn(),
            rich.progress.TransferSpeedColumn(),
        ) as progress:
            download_task = progress.add_task(f"Download", total=total)
            for chunk in response.iter_bytes():
                content.append(chunk)
                progress.update(download_task, completed=response.num_bytes_downloaded)

    CACHED_PYZ.write_bytes(b"".join(content))
    return True


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


def print_pip_version() -> int:
    args = ["--disable-pip-version-check", "--version"]
    return subprocess.run(
        [sys.executable, os.fsdecode(CACHED_PYZ), *args], check=False
    ).returncode


def select_dir() -> pathlib.Path:
    cwd = pathlib.Path.cwd()
    locations = [cwd, *cwd.parents]
    for path in locations:
        pyproject_toml = path / "pyproject.toml"
        if pyproject_toml.exists():
            break
    else:
        # TODO: error condition
        print("No pyproject.toml found.")
    return path


def main():
    console = rich.console.Console()
    background_output = False
    downloaded_pyz = False

    if not CACHED_PYZ.exists():
        background_output = True
        console.rule("Download pip")
        # TODO: error condition
        blocking_download()
        downloaded_pyz = True
        # TODO: error condition
        print_pip_version()

    if in_virtual_env():
        py_path = pathlib.Path(sys.executable)
    else:
        background_output = True
        console.rule("Create virtual environment")
        # TODO: error condition
        workspace_path = select_dir()
        print("Creating virtual environment in", workspace_path)
        # TODO: error condition
        py_path = create_venv(workspace_path)

    if background_output:
        console.rule("pip output")

    exit_code = pip(py_path, CACHED_PYZ, args=sys.argv[1:])

    if not downloaded_pyz:
        # XXX Don't output unless pip was updated.
        console.rule("Update pip")
        if background_download():
            # XXX error condition
            print_pip_version()

    # TODO: guarantee to exit with the same code as pip?
    sys.exit(exit_code)

    # TODO: asynchronously execute pip and check/download a new pip simultaneously.
    # TODO: Only show download progress if still occurring after pip execution finishes.


if __name__ == "__main__":
    main()
