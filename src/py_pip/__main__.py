import xdg

from . import download


def main():
    pyz_bytes = download.download_pyz()
    cache_dir = xdg.xdg_cache_home() / "py-pip"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pyz_path = cache_dir / "pip.pyz"
    pyz_path.write_bytes(pyz_bytes)
    print("Saved to", pyz_path)


if __name__ == "__main__":
    main()
