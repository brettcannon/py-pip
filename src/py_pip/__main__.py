import xdg_base_dirs as xdg

from . import download


def main():
    print("Downloading pip.pyz ... ", end="")
    pyz_bytes = download.download_pyz()
    print(f"{len(pyz_bytes):,} bytes")
    cache_dir = xdg.xdg_cache_home() / "py-pip"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pyz_path = cache_dir / "pip.pyz"
    print("Saving to", pyz_path, "...")
    pyz_path.write_bytes(pyz_bytes)


if  __name__ == "__main__":
    main()
