import os
import pathlib

import httpx
import rich.progress
import xdg


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"


def pyz_path() -> pathlib.Path:
    cache_dir = xdg.xdg_cache_home() / "py-pip"
    return cache_dir / "pip.pyz"


def download_pyz() -> bytes:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    with httpx.stream(http_verb, PYZ_URL) as response:
        response.raise_for_status()

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
