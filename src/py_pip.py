import functools
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
import trio
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


async def background_download(pip_done: trio.Event) -> bool:
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

    # XXX download async: https://www.python-httpx.org/async/
    with httpx.stream(http_verb, PYZ_URL, headers=headers) as response:
        # XXX handle errors

        if response.status_code == 304:
            return False

        headers_cache.write_text(json.dumps(dict(response.headers)), encoding="utf-8")

        content = []
        printed_separator = False
        total = int(response.headers["Content-Length"])

        with rich.progress.Progress(
            "[progress.percentage]{task.percentage:>3.0f}%",
            rich.progress.BarColumn(bar_width=None),
            rich.progress.DownloadColumn(),
            rich.progress.TransferSpeedColumn(),
        ) as progress:
            download_task = progress.add_task(
                f"Download", total=total, visible=pip_done.is_set()
            )
            for chunk in response.iter_bytes():
                content.append(chunk)
                if not printed_separator and pip_done.is_set():
                    rich.console.Console().rule("updating pip")
                    printed_separator = True
                progress.update(
                    download_task,
                    completed=response.num_bytes_downloaded,
                    visible=pip_done.is_set(),
                )

    CACHED_PYZ.write_bytes(b"".join(content))
    if pip_done.is_set():
        # XXX error condition
        print_pip_version()
    return True


def in_virtual_env() -> bool:
    return sys.prefix != sys.base_prefix


def create_venv(path: pathlib.Path) -> pathlib.Path:
    microvenv.create(path / ".venv")
    return path / ".venv" / "bin" / "python"


async def pip(
    py_path: pathlib.Path,
    args: List[str],
    *,
    exit: trio.MemorySendChannel,
    done: trio.Event,
) -> int:
    args = ["--disable-pip-version-check", "--require-virtualenv", *args]
    with exit:
        # XXX Execute asynchronously
        exit_code = subprocess.run(
            [os.fsdecode(py_path), os.fsdecode(CACHED_PYZ), *args], check=False
        ).returncode
        await exit.send(exit_code)
        done.set()


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
        # XXX: error condition
        print("No pyproject.toml found.")
    return path


async def real_main():
    console = rich.console.Console()
    background_output = False
    downloaded_pyz = False

    if not CACHED_PYZ.exists():
        background_output = True
        console.rule("Download pip")
        # XXX: error condition
        blocking_download()
        downloaded_pyz = True
        # XXX: error condition
        print_pip_version()

    if in_virtual_env():
        py_path = pathlib.Path(sys.executable)
    else:
        background_output = True
        console.rule("Create virtual environment")
        # XXX: error condition
        workspace_path = select_dir()
        print("Creating virtual environment in", workspace_path)
        # XXX: error condition
        py_path = create_venv(workspace_path)

    if background_output:
        console.rule("pip output")

    exit_code_send, exit_code_receive = trio.open_memory_channel(1)
    pip_done = trio.Event()

    exec_pip = functools.partial(
        pip, py_path, args=sys.argv[1:], exit=exit_code_send, done=pip_done
    )
    exec_download = functools.partial(background_download, pip_done)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(exec_pip)
        if not downloaded_pyz:
            nursery.start_soon(exec_download)

    with exit_code_receive:
        sys.exit(await exit_code_receive.receive())


def main():
    trio.run(real_main)


if __name__ == "__main__":
    main()
