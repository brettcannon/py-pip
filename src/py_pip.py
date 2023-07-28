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


def failure(message: str, /) -> None:
    """Print a failure message and exit."""
    console = rich.console.Console()
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)


def in_virtual_env() -> bool:
    return sys.prefix != sys.base_prefix


def select_dir() -> pathlib.Path:
    cwd = pathlib.Path.cwd()
    locations = [cwd, *cwd.parents]
    for path in locations:
        # TODO: log
        pyproject_toml = path / "pyproject.toml"
        if pyproject_toml.exists():
            # TODO: log
            break
    else:
        failure("No pyproject.toml found.")
    return path


def create_venv(path: pathlib.Path) -> pathlib.Path:
    # TODO: log
    try:
        microvenv.create(path / ".venv")
    except OSError as exc:
        failure(str(exc))
    return path / ".venv" / "bin" / "python"


def print_pip_version() -> int:
    args = ["--disable-pip-version-check", "--version"]
    # TODO: log
    proc = subprocess.run([sys.executable, os.fsdecode(CACHED_PYZ), *args], check=False)
    if proc.returncode != 0:
        failure(f"pip --version returned {proc.returncode}")


async def pip(
    py_path: pathlib.Path,
    args: List[str],
    *,
    exit: trio.MemorySendChannel,
    done: trio.Event,
) -> int:
    args = ["--disable-pip-version-check", "--require-virtualenv", *args]
    with exit:
        # TODO: log
        proc = await trio.run_process(
            [os.fsdecode(py_path), os.fsdecode(CACHED_PYZ), *args], check=False
        )
        await exit.send(proc.returncode)
        done.set()


def blocking_download() -> None:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers_cache = CACHE_DIR / "response_headers.json"

    # TODO: log URL
    with httpx.stream(http_verb, PYZ_URL) as response:
        if response.status_code != 200:
            failure(f"{http_verb} {PYZ_URL} returned {response.status_code}")

        # TODO: log
        headers_cache.parent.mkdir(parents=True, exist_ok=True)
        headers_cache.write_text(json.dumps(dict(response.headers)), encoding="utf-8")

        content = []
        # TODO: log
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

    # TODO: log
    CACHED_PYZ.write_bytes(b"".join(content))


async def background_download(pip_done: trio.Event) -> bool:
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers_cache = CACHE_DIR / "response_headers.json"
    headers = {}
    if headers_cache.exists():
        # TODO: log
        last_headers = json.loads(headers_cache.read_text(encoding="utf-8"))
        try:
            # TODO: log
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests
            headers["If-Modified-Since"] = last_headers["last-modified"]
            headers["If-None-Match"] = last_headers["etag"]
        except KeyError:
            pass

    client = httpx.AsyncClient()
    # TODO: log
    async with client.stream(http_verb, PYZ_URL, headers=headers) as response:
        content = []

        if response.status_code == 304:
            # TODO: log
            return False
        elif response.status_code == 200:
            # TODO: log
            headers_cache.write_text(
                json.dumps(dict(response.headers)), encoding="utf-8"
            )
            printed_separator = False
            # TODO: log
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
                async for chunk in response.aiter_bytes():
                    content.append(chunk)
                    if not printed_separator and pip_done.is_set():
                        rich.console.Console().rule("updating pip")
                        printed_separator = True
                    progress.update(
                        download_task,
                        completed=response.num_bytes_downloaded,
                        visible=pip_done.is_set(),
                    )

    await pip_done.wait()
    if not printed_separator:
        rich.console.Console().rule("updating pip")
    if not content:
        failure(f"{http_verb} {PYZ_URL} returned {response.status_code}")
    else:
        # TODO: log
        CACHED_PYZ.write_bytes(b"".join(content))
    print_pip_version()
    return True


async def real_main():
    console = rich.console.Console()
    background_output = False
    downloaded_pyz = False

    if not CACHED_PYZ.exists():
        # TODO: log
        background_output = True
        console.rule("Download pip")
        blocking_download()
        downloaded_pyz = True
        print_pip_version()

    if in_virtual_env():
        # TODO: log
        py_path = pathlib.Path(sys.executable)
    else:
        background_output = True
        console.rule("Create virtual environment")
        workspace_path = select_dir()
        print("Creating virtual environment in", workspace_path)
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
        exit_code = await exit_code_receive.receive()
        # TODO: log
        sys.exit(exit_code)


def main():
    trio.run(real_main)


if __name__ == "__main__":
    main()
