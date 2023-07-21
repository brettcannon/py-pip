import json
import os
import pathlib
import shutil
from typing import Optional

import httpx
import rich.progress
import xdg


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"
CACHE_DIR = xdg.xdg_cache_home() / "py-pip"


def pyz_path() -> pathlib.Path:
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
