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


def calc_pyz_path() -> pathlib.Path:
    return CACHE_DIR / "pip.pyz"


def download_pyz() -> Optional[bytes]:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers = {}
    headers_cache = CACHE_DIR / "response_headers.json"
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
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return None

        headers_cache.parent.mkdir(parents=True, exist_ok=True)
        headers_cache.write_text(json.dumps(dict(response.headers)), encoding="utf-8")

        content = []
        total = int(response.headers["Content-Length"])

        print("Downloading", PYZ_URL)
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

    return b"".join(content)


def save_pyz(path: pathlib.Path, data: bytes) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


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
    pyz_path = calc_pyz_path()
    # TODO: error condition
    pyz_bytes = download_pyz()
    if not pyz_bytes:
        print("Reusing", pyz_path)
    else:
        save_pyz(pyz_path, pyz_bytes)
        # TODO: error condition
        pip(sys.executable, pyz_path, args=["--version"])

    if in_virtual_env():
        py_path = pathlib.Path(sys.executable)
    else:
        # TODO: error condition
        workspace_path = select_dir()
        print("Creating virtual environment in", workspace_path)
        # TODO: error condition
        py_path = create_venv(workspace_path)

    console = rich.console.Console()
    console.rule("pip output")

    sys.exit(pip(py_path, pyz_path, args=sys.argv[1:]))

    # Check if `.pyz` is cached.
    # Download if necessary.
    # Execute pip.
    # Check/download a new pip.
    # Show spinner if download isn't complete.
    # If pip updated, print the new version.


if __name__ == "__main__":
    main()
