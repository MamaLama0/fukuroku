"""Textes de l'interface, repris des fichiers de langue d'origine (``language.xx.loc``).

Les clés sont celles du logiciel d'origine (ex. ``SETTINGS_NL_CheckBox_Show_RNG``).
Le nom du produit est remplacé par celui de Fukuroku.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from . import APP_NAME, assets

LANGUAGES = {
    "fr": "Français", "en": "English", "es": "Español", "it": "Italiano", "pt": "Português",
    "ru": "Русский", "ua": "Українська", "hi": "हिन्दी", "jp": "日本語", "zh": "中文",
}
FLAGS = {"fr": "fr", "en": "en", "es": "es", "it": "it", "pt": "pt", "ru": "ru", "ua": "ru", "hi": "hi",
         "jp": "jp", "zh": "zh"}

_NS = "{http://jurojinpoker.com/locale}"
_PRODUCT = re.compile(r"Jurojin\s*Poker|Jurojin|JUROJIN|Juro\b")
_cache: dict[str, dict[str, str]] = {}
_current = "fr"


def _load(lang: str) -> dict[str, str]:
    if lang not in _cache:
        table: dict[str, str] = {}
        p = assets.path("locale", f"language.{lang}.loc")
        if p.exists():
            for el in ET.parse(p).getroot().iter(_NS + "add"):
                key, value = el.get("key"), el.get("value") or ""
                if key:
                    table[key] = _PRODUCT.sub(APP_NAME, value)
        _cache[lang] = table
    return _cache[lang]


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in LANGUAGES else "en"


def language() -> str:
    return _current


def tr(key: str, default: str | None = None) -> str:
    """Texte traduit ; repli sur l'anglais puis sur ``default`` (ou la clé)."""
    value = _load(_current).get(key) or _load("en").get(key)
    return value if value else (default if default is not None else key)


def has(key: str) -> bool:
    return bool(_load(_current).get(key) or _load("en").get(key))
