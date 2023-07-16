import os


import httpx
from tqdm import tqdm
import xdg


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"


def download_pyz() -> bytes:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    with httpx.stream(http_verb, PYZ_URL) as response:
        content = []
        total = int(response.headers["Content-Length"])

        with tqdm(
            desc=f"{http_verb} {PYZ_URL}",
            total=total,
            unit_scale=True,
            unit_divisor=1024,
            unit="B",
        ) as progress:
            num_bytes_downloaded = response.num_bytes_downloaded
            for chunk in response.iter_bytes():
                content.append(chunk)
                progress.update(response.num_bytes_downloaded - num_bytes_downloaded)
                num_bytes_downloaded = response.num_bytes_downloaded
    response.raise_for_status()
    return b"".join(content)


def save_pyz(data: bytes) -> str:
    cache_dir = xdg.xdg_cache_home() / "py-pip"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pyz_path = cache_dir / "pip.pyz"
    pyz_path.write_bytes(data)
    print("Saved to", pyz_path)
    return os.fsdecode(pyz_path)
