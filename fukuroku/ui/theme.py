"""Thème visuel repris du logiciel d'origine (Jurojin.Style : AppColors, polices).

Palette extraite de ``Styles/AppColors.xaml`` : violet primaire #7652F8,
menu latéral #6643DD (sélection #30268E), gris, vert, jaune, rouge, bleu.
Polices : Montserrat (interface), Digital-7 Mono (RNG, minuteur).
"""

from __future__ import annotations

import ctypes
import logging
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .. import assets

log = logging.getLogger("fukuroku")

# --- AppColors.xaml -------------------------------------------------------------
GRAY = {50: "#FAFAFF", 100: "#F0F5FF", 200: "#E1E6F5", 300: "#CDD5E1", 400: "#ABB2BD", 500: "#8C929C",
        600: "#6B727A", 700: "#4B5057", 800: "#2D3238", 900: "#222429"}
PRIMARY = {50: "#EEEEFF", 75: "#E8E5FF", 100: "#DDDBFF", 200: "#C9C5FF", 300: "#B4B0FF", 400: "#9791FF",
           500: "#7652F8", 600: "#6643DD", 700: "#4738B9", 800: "#30268E", 900: "#1B185A", 950: "#171B36"}
GREEN = {50: "#E5F9EC", 100: "#B0ECC6", 200: "#7CE0A0", 300: "#5CCC84", 400: "#3CB869", 500: "#2E9F57",
         600: "#1F8544", 700: "#1E6638"}
YELLOW = {50: "#FFF3CC", 100: "#FFDC6B", 300: "#FFC300", 400: "#F3AE00", 500: "#E69200", 600: "#BD7800"}
RED = {50: "#FFDCDC", 100: "#FFBABA", 300: "#FF7587", 400: "#FF3F62", 500: "#E33151", 600: "#C10039"}
ORANGE = {300: "#FC9964", 400: "#FC8546", 500: "#DD6E33"}
BLUE = {50: "#E2F8FF", 100: "#A9EBFF", 300: "#76D5FD", 400: "#53BFFB", 500: "#19ADFF", 600: "#1295DE", 700: "#0E77B2"}

SIDE_MENU = "#6643DD"
SIDE_MENU_SELECTED = "#30268E"
WINDOW_BG = "#FFFFFF"
PAGE_BG = GRAY[50]
TEXT = GRAY[900]
TEXT_MUTED = GRAY[600]
BORDER = GRAY[200]
ACCENT = PRIMARY[500]
DARK = PRIMARY[950]
GRADIENT_PURPLE = ("#A78FFF", "#535AFB")
GRADIENT_DARK = ("#171B36", "#4C44BA")

# Dimensions de la fenêtre principale (AppWindowN : 1302 × 664, menu 60 / 194 px).
WINDOW_SIZE = (1302, 664)
MENU_WIDTH, MENU_EXPANDED_WIDTH = 60, 194

FONT_FAMILY = "Segoe UI"
DIGITAL_FAMILY = "Courier"


def _register_font_file(path) -> bool:
    """Rend une police .ttf disponible pour ce processus uniquement (aucune installation)."""
    try:
        if sys.platform == "win32":
            FR_PRIVATE = 0x10
            return ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0) > 0
        if sys.platform == "darwin":
            cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            ct = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreText.framework/CoreText")
            cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
            cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                                                   ctypes.c_bool]
            ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
            raw = str(path).encode()
            url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
            return bool(ct.CTFontManagerRegisterFontsForURL(url, 1, None))
        fc = ctypes.cdll.LoadLibrary("libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        return bool(fc.FcConfigAppFontAddFile(None, str(path).encode()))
    except Exception as exc:  # police facultative : repli sur la police système
        log.debug("police %s non chargée : %s", path, exc)
        return False


def register_fonts() -> None:
    """À appeler avant la création de la fenêtre Tk."""
    for name in ("Montserrat.ttf", "Digital7Mono.ttf", "Technology.ttf"):
        _register_font_file(assets.path("fonts", name))


def resolve_fonts(root: tk.Misc) -> None:
    global FONT_FAMILY, DIGITAL_FAMILY
    families = set(tkfont.families(root))
    for candidate in ("Montserrat", "Montserrat Medium", "Segoe UI", "Helvetica Neue", "Helvetica", "DejaVu Sans"):
        if candidate in families:
            FONT_FAMILY = candidate
            break
    for candidate in ("Digital-7 Mono", "Digital-7", "Technology", "Courier New", "Courier"):
        if candidate in families:
            DIGITAL_FAMILY = candidate
            break


def font(size: int = 10, weight: str = "normal") -> tuple:
    return (FONT_FAMILY, size, weight)


def digital(size: int = 28) -> tuple:
    return (DIGITAL_FAMILY, size)


# --- images ---------------------------------------------------------------------
_images: dict[tuple, tk.PhotoImage] = {}


def image(name: str, size: int | tuple[int, int] | None = None) -> tk.PhotoImage | None:
    """Image d'origine (``assets/images/<name>``), redimensionnée et mise en cache."""
    key = (name, size)
    if key in _images:
        return _images[key]
    path = assets.path("images", name)
    if not path.exists():
        return None
    try:
        from PIL import Image, ImageTk
        im = Image.open(path).convert("RGBA")
        if size:
            box = (size, size) if isinstance(size, int) else size
            im.thumbnail(box, Image.LANCZOS)
        photo = ImageTk.PhotoImage(im)
    except ImportError:
        photo = tk.PhotoImage(file=str(path))
        if size:
            target = size if isinstance(size, int) else max(size)
            factor = max(1, round(max(photo.width(), photo.height()) / max(1, target)))
            photo = photo.subsample(factor, factor)
    except Exception as exc:
        log.debug("image %s : %s", name, exc)
        return None
    _images[key] = photo
    return photo


# --- styles ttk -----------------------------------------------------------------
def apply(root: tk.Tk) -> ttk.Style:
    resolve_fonts(root)
    root.configure(bg=WINDOW_BG)
    root.option_add("*Font", font(10))
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure(".", background=WINDOW_BG, foreground=TEXT, font=font(10), bordercolor=BORDER,
                    focuscolor=ACCENT, lightcolor=WINDOW_BG, darkcolor=WINDOW_BG)
    style.configure("TFrame", background=WINDOW_BG)
    style.configure("Page.TFrame", background=PAGE_BG)
    style.configure("TLabel", background=WINDOW_BG, foreground=TEXT)
    style.configure("Muted.TLabel", foreground=TEXT_MUTED)
    style.configure("TCheckbutton", background=WINDOW_BG, foreground=TEXT, indicatorcolor=WINDOW_BG,
                    indicatorbackground=WINDOW_BG)
    style.map("TCheckbutton", indicatorcolor=[("selected", ACCENT)], background=[("active", WINDOW_BG)])
    style.configure("TRadiobutton", background=WINDOW_BG, foreground=TEXT, indicatorcolor=WINDOW_BG)
    style.map("TRadiobutton", indicatorcolor=[("selected", ACCENT)], background=[("active", WINDOW_BG)])
    style.configure("TEntry", fieldbackground=GRAY[100], bordercolor=GRAY[300], lightcolor=GRAY[100], padding=6)
    style.map("TEntry", bordercolor=[("focus", ACCENT)])
    style.configure("TSpinbox", fieldbackground=GRAY[100], bordercolor=GRAY[300], arrowsize=12, padding=4)
    style.configure("TCombobox", fieldbackground=GRAY[100], bordercolor=GRAY[300], arrowsize=14, padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", GRAY[100])], selectbackground=[("readonly", GRAY[100])],
              selectforeground=[("readonly", TEXT)])
    style.configure("Treeview", background=WINDOW_BG, fieldbackground=WINDOW_BG, foreground=TEXT, rowheight=30,
                    bordercolor=BORDER, font=font(10))
    style.configure("Treeview.Heading", background=PRIMARY[50], foreground=PRIMARY[800], font=font(9, "bold"),
                    relief="flat", padding=6)
    style.map("Treeview", background=[("selected", PRIMARY[100])], foreground=[("selected", PRIMARY[900])])
    style.configure("Vertical.TScrollbar", background=GRAY[200], troughcolor=WINDOW_BG, bordercolor=WINDOW_BG,
                    arrowcolor=GRAY[500], gripcount=0)
    style.configure("Horizontal.TScale", background=ACCENT, troughcolor=GRAY[200])
    root.option_add("*TCombobox*Listbox.font", font(10))
    root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY[100])
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    return style
