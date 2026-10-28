"""Construit l'exécutable Fukuroku pour la plateforme courante avec PyInstaller.

    python packaging/build.py

Résultat dans ``dist/`` : ``Fukuroku.exe`` (Windows), ``Fukuroku`` (Linux),
``Fukuroku.app`` (macOS), puis une archive prête à publier.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "fukuroku" / "assets"
BUILD = ROOT / "build"
DIST = ROOT / "dist"


def version() -> str:
    for line in (ROOT / "fukuroku" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=")[1].strip().strip('"')
    return "0"


def mac_icon() -> Path:
    """Icône .icns générée depuis le logo d'origine."""
    from PIL import Image
    out = BUILD / "Fukuroku.icns"
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(ASSETS / "images" / "logo.png").convert("RGBA")
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    square.resize((512, 512), Image.LANCZOS).save(out)
    return out


def main() -> int:
    system = platform.system()
    sep = ";" if system == "Windows" else ":"
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Fukuroku",
        "--workpath", str(BUILD), "--distpath", str(DIST), "--specpath", str(BUILD),
        "--add-data", f"{ASSETS}{sep}fukuroku/assets",
        "--collect-submodules", "pynput",
        "--hidden-import", "PIL._tkinter_finder",
    ]
    if system == "Windows":
        args += ["--onefile", "--icon", str(ASSETS / "images" / "app.ico")]
    elif system == "Darwin":
        args += ["--onedir", "--icon", str(mac_icon()), "--osx-bundle-identifier", "org.fukuroku.app"]
    else:
        args += ["--onefile"]
    try:
        import pystray  # noqa: F401
        args += ["--collect-submodules", "pystray"]
    except ImportError:
        pass
    args.append(str(ROOT / "packaging" / "launcher.py"))
    print(" ".join(args))
    subprocess.run(args, check=True, cwd=ROOT)

    v, arch = version(), platform.machine().lower() or "x86_64"
    if system == "Windows":
        archive = DIST / f"Fukuroku-{v}-windows-{arch}.zip"
        shutil.make_archive(str(archive.with_suffix("")), "zip", DIST, "Fukuroku.exe")
    elif system == "Darwin":
        archive = DIST / f"Fukuroku-{v}-macos-{arch}.zip"
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", "Fukuroku.app", archive.name],
                       check=True, cwd=DIST)
    else:
        archive = DIST / f"Fukuroku-{v}-linux-{arch}.tar.gz"
        shutil.make_archive(str(archive).removesuffix(".tar.gz"), "gztar", DIST, "Fukuroku")
    print(f"→ {archive}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"archive={archive}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
