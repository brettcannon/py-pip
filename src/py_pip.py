import functools
import json
import logging
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
import structlog
import trio
import xdg


LOGGER = structlog.get_logger()
_LOG_LEVELS = [logging.ERROR, logging.INFO, logging.DEBUG]
_LOGGING_LEVEL = os.environ.get("PY_PIP_DEBUG") or 0
_MAX_LOG_LEVEL = len(_LOG_LEVELS) - 1
try:
    _LOGGING_LEVEL = max(min(int(_LOGGING_LEVEL), _MAX_LOG_LEVEL), 0)
except ValueError:
    _LOGGING_LEVEL = _MAX_LOG_LEVEL
_CHOSEN_lOG_LEVEL = _LOG_LEVELS[_LOGGING_LEVEL]
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(_CHOSEN_lOG_LEVEL)
)
del _LOG_LEVELS, _LOGGING_LEVEL, _CHOSEN_lOG_LEVEL, _MAX_LOG_LEVEL
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
    """Find the (parent) directory with a `pyproject.toml` file."""
    cwd = pathlib.Path.cwd()
    locations = [cwd, *cwd.parents]
    for path in locations:
        LOGGER.debug("checking for pyproject.toml", path=path)
        pyproject_toml = path / "pyproject.toml"
        if pyproject_toml.exists():
            LOGGER.info("found pyproject.toml", path=path)
            break
    else:
        failure("No pyproject.toml found.")
    return path


def create_venv(path: pathlib.Path) -> pathlib.Path:
    venv_path = path / ".venv"
    try:
        microvenv.create()
        LOGGER.info("created virtual environment", path=venv_path)
    except OSError as exc:
        failure(str(exc))
    return path / ".venv" / "bin" / "python"


def print_pip_version() -> int:
    """Print the version of `pip.pyz` and return the exit code."""
    executable = sys.executable
    pip_path = os.fsdecode(CACHED_PYZ)
    args = ["--disable-pip-version-check", "--version"]
    proc = subprocess.run([executable, pip_path, *args], check=False)
    return_code = proc.returncode
    LOGGER.info(
        "pip version",
        executable=executable,
        pip=pip_path,
        args=args,
        return_code=return_code,
    )
    if return_code != 0:
        failure(f"pip --version returned {proc.returncode}")


async def pip(
    py_path: pathlib.Path,
    args: List[str],
    *,
    exit: trio.MemorySendChannel,
    done: trio.Event,
) -> int:
    """Execute `pip.pyz`.

    Completion of execution is signaled via setting `done`. The exit code is
    communicated via `exit`.
    """
    args = ["--disable-pip-version-check", "--require-virtualenv", *args]
    executable = os.fsdecode(py_path)
    pip_path = os.fsdecode(CACHED_PYZ)
    with exit:
        proc = await trio.run_process([executable, pip_path, *args], check=False)
        return_code = proc.returncode
        LOGGER.info(
            "executed pip",
            executable=executable,
            pip=pip_path,
            args=args,
            return_code=return_code,
        )
        await exit.send(return_code)
        done.set()


def blocking_download() -> None:
    """Actively download `pip.pyz`."""
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers_cache = CACHE_DIR / "response_headers.json"

    with httpx.stream(http_verb, PYZ_URL) as response:
        status_code = response.status_code
        headers = dict(response.headers)
        LOGGER.info(
            "downloading pip",
            verb=http_verb,
            url=PYZ_URL,
            headers=headers,
            status=status_code,
        )
        if status_code != 200:
            failure(f"{http_verb} {PYZ_URL} returned {status_code}")

        LOGGER.info("creating directories", path=headers_cache.parent)
        headers_cache.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info("writing headers", path=headers_cache, headers=headers)
        headers_cache.write_text(json.dumps(headers), encoding="utf-8")

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

    total_contents = b"".join(content)
    LOGGER.info("writing pip", path=CACHED_PYZ, size=len(total_contents))
    CACHED_PYZ.write_bytes(total_contents)


async def background_download(pip_done: trio.Event) -> bool:
    """Download `pip.pyz`, if necessary, in the background.

    Download progress is only displayed if/when `pip_done` is set. If there's any update
    to pip then its version will be printed once pip is done executing.
    """
    # (Mostly) from https://www.python-httpx.org/advanced/#monitoring-download-progress .
    http_verb = "GET"
    headers_cache = CACHE_DIR / "response_headers.json"
    headers = {}
    if headers_cache.exists():
        LOGGER.info("reading headers", path=headers_cache)
        last_headers = json.loads(headers_cache.read_text(encoding="utf-8"))
        try:
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests
            headers["If-Modified-Since"] = last_headers["last-modified"]
            headers["If-None-Match"] = last_headers["etag"]
        except KeyError:
            pass

    client = httpx.AsyncClient()
    async with client.stream(http_verb, PYZ_URL, headers=headers) as response:
        status_code = response.status_code
        response_headers = dict(response.headers)
        LOGGER.info(
            "downloading pip asynchronously",
            verb=http_verb,
            url=PYZ_URL,
            response=response_headers,
            status=status_code,
        )

        content = []

        if status_code == 304:
            LOGGER.debug("pip is up to date")
            return False
        elif status_code == 200:
            LOGGER.info("caching headers", path=headers_cache)
            headers_cache.write_text(json.dumps(response_headers), encoding="utf-8")
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
        LOGGER.info("writing pip", path=CACHED_PYZ, size=len(content))
        # Don't overwrite `pip.pyz` until pip is done executing.
        CACHED_PYZ.write_bytes(b"".join(content))
    print_pip_version()
    return True


async def real_main(args: List[str]):
    console = rich.console.Console()
    background_output = False
    downloaded_pyz = False

    if not CACHED_PYZ.exists():
        LOGGER.debug("pip.pyz does not exist")
        background_output = True
        console.rule("Download pip")
        blocking_download()
        downloaded_pyz = True
        print_pip_version()

    if in_virtual_env():
        LOGGER.debug("in virtual environment")
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
        LOGGER.debug("exit code", exit_code=exit_code)
        sys.exit(exit_code)


def main(args: List[str] = sys.argv[1:]) -> None:
    """Synchronous wrapper for real_main()."""
    trio.run(real_main, args)


if __name__ == "__main__":
    main()
