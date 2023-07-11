import httpx
import rich.progress


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"


def download_pyz() -> bytes:
    with httpx.stream("GET", PYZ_URL) as response:
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
