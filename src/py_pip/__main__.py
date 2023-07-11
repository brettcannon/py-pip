import sys

import xdg

from . import download
from . import run


def main():
    pyz_bytes = download.download_pyz()
    pyz = download.save_pyz(pyz_bytes)
    sys.exit(run.pip(pyz, args=sys.argv[1:]))


if __name__ == "__main__":
    main()
