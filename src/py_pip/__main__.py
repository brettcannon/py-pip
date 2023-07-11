import xdg

from . import download


def main():
    pyz_bytes = download.download_pyz()
    download.save_pyz(pyz_bytes)


if __name__ == "__main__":
    main()
