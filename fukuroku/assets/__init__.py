"""Ressources du logiciel d'origine (sons, images, polices, textes, layouts prédéfinis).

Les fichiers sont lus depuis ce dossier, y compris dans un exécutable PyInstaller.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def sounds() -> dict[str, Path]:
    """Sons d'alerte d'origine, par nom (« Bell », « Bubble »…)."""
    return {p.stem: p for p in sorted((ROOT / "sounds").glob("*.wav"))}
