import httpx
import os
import rich.progress
import xdg


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"


def download_pyz() -> bytes:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    with httpx.stream("GET", PYZ_URL) as response:
        print("Downloading", PYZ_URL)
        content = []
        total = int(response.headers["Content-Length"])

        with rich.progress.Progress(
            "[progress.percentage]{task.percentage:>3.0f}%",
            rich.progress.BarColumn(bar_width=None),
            rich.progress.DownloadColumn(),
            rich.progress.TransferSpeedColumn(),
        ) as progress:
            download_task = progress.add_task("Download", total=total)
            for chunk in response.iter_bytes():
                content.append(chunk)
                progress.update(download_task, completed=response.num_bytes_downloaded)
    response.raise_for_status()
    return b"".join(content)


def save_pyz(data: bytes) -> str:
    cache_dir = xdg.xdg_cache_home() / "py-pip"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pyz_path = cache_dir / "pip.pyz"
    pyz_path.write_bytes(data)
    print("Saved to", pyz_path)
    return os.fsdecode(pyz_path)
