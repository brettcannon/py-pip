import sys

import rich.console
import xdg

from . import download
from . import run


def main():
    pyz_bytes = download.download_pyz()
    pyz = download.save_pyz(pyz_bytes)

    print()
    console = rich.console.Console()
    console.rule("pip output")

    sys.exit(run.pip(pyz, args=sys.argv[1:]))


if __name__ == "__main__":
    main()
