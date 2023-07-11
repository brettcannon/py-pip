import subprocess
import sys
from typing import List


def pip(pyz_path: str, args: List[str]) -> int:
    args.insert(0, "--disable-pip-version-check")
    return subprocess.run([sys.executable, pyz_path, *args], check=False).returncode
