import httpx


PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"

def download_pyz() -> bytes:
    response = httpx.get(PYZ_URL, follow_redirects=True)
    response.raise_for_status()
    return response.content
