import pathlib
import sys

import rich.console
import xdg

from . import download
from . import run


def main():
    pyz_path = download.pyz_path()
    if pyz_path.exists():
        print(f"Using {pyz_path}")
    else:
        pyz_bytes = download.download_pyz()
        download.save_pyz(pyz_path, pyz_bytes)
        print("Saved to", pyz_path.parent)

    py_path = (
        run.create_venv() if not run.in_virtual_env() else pathlib.Path(sys.executable)
    )

    console = rich.console.Console()
    console.rule("pip output")

    sys.exit(run.pip(py_path, pyz_path, args=sys.argv[1:]))


if __name__ == "__main__":
    main()
