"""Écoute globale clavier/souris (LowLevelHooker) via pynput.

pynput fonctionne sous Windows, macOS (permission « Surveillance de
l'entrée » requise) et Linux/X11.  Les touches ne sont pas interceptées :
elles atteignent aussi l'application au premier plan.
"""

from __future__ import annotations

import logging
from typing import Callable

from .hotkeys import HotKey

log = logging.getLogger("fukuroku")

_MOD_KEYS = {
    "ctrl": ("ctrl", "ctrl_l", "ctrl_r"),
    "alt": ("alt", "alt_l", "alt_r", "alt_gr"),
    "shift": ("shift", "shift_l", "shift_r"),
    "cmd": ("cmd", "cmd_l", "cmd_r"),
}
_MOD_LOOKUP = {name: mod for mod, names in _MOD_KEYS.items() for name in names}
_SPECIAL = {"esc": "escape", "page_up": "page_up", "page_down": "page_down"}


def key_to_name(key) -> str | None:
    """Nom normalisé d'une touche pynput (``Key`` ou ``KeyCode``)."""
    name = getattr(key, "name", None)
    if name:
        return _MOD_LOOKUP.get(name, _SPECIAL.get(name, name))
    vk = getattr(key, "vk", None)
    char = getattr(key, "char", None)
    if vk is not None and (65 <= vk <= 90 or 48 <= vk <= 57):
        return chr(vk).lower()
    if char and char.isprintable():
        return char.lower()
    if vk is not None and 96 <= vk <= 105:  # pavé numérique Windows
        return f"num{vk - 96}"
    return None


def mouse_button_name(button) -> str | None:
    name = getattr(button, "name", str(button))
    return {"left": "mouse_left", "right": "mouse_right", "middle": "mouse_middle", "x1": "mouse4", "x2": "mouse5",
            "button8": "mouse4", "button9": "mouse5"}.get(name)


class ChordTracker:
    """Construit les HotKey à partir des événements bruts (testable sans pynput)."""

    def __init__(self, on_hotkey: Callable[[HotKey], None]):
        self.on_hotkey = on_hotkey
        self.mods: set[str] = set()
        self.down: set[str] = set()

    def press(self, name: str | None) -> None:
        if not name:
            return
        if name in _MOD_KEYS:
            self.mods.add(name)
            return
        if name in self.down:  # auto-répétition
            return
        self.down.add(name)
        self.on_hotkey(HotKey(frozenset(self.mods), name))

    def release(self, name: str | None) -> None:
        if not name:
            return
        self.mods.discard(name)
        self.down.discard(name)

    def tap(self, name: str) -> None:
        """Entrée sans relâchement (molette, boutons souris)."""
        self.on_hotkey(HotKey(frozenset(self.mods), name))


class InputListener:
    def __init__(self, on_hotkey: Callable[[HotKey], None], mouse_buttons: bool = True):
        self._dispatch = on_hotkey
        self.tracker = ChordTracker(self._emit)
        self.mouse_buttons = mouse_buttons
        self._listeners = []
        self.error: str | None = None
        self.capture: Callable[[HotKey], None] | None = None  # saisie d'un raccourci dans l'UI

    def _emit(self, hk: HotKey) -> None:
        if self.capture is not None:
            cb, self.capture = self.capture, None
            cb(hk)
        else:
            self._dispatch(hk)

    def start(self) -> bool:
        try:
            from pynput import keyboard, mouse
        except Exception as exc:  # ImportError ou absence de serveur X
            self.error = f"pynput indisponible ({exc}) : pip install pynput"
            log.warning(self.error)
            return False
        def on_press(key):
            self.tracker.press(key_to_name(key))

        def on_release(key):
            self.tracker.release(key_to_name(key))

        def on_click(x, y, button, pressed):
            name = mouse_button_name(button)
            if pressed and name and (name not in ("mouse_left", "mouse_right") or self.tracker.mods):
                self.tracker.tap(name)

        def on_scroll(x, y, dx, dy):
            if dy:
                self.tracker.tap("wheel_up" if dy > 0 else "wheel_down")

        try:
            kb = keyboard.Listener(on_press=on_press, on_release=on_release)
            kb.start()
            self._listeners.append(kb)
            if self.mouse_buttons:
                ms = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
                ms.start()
                self._listeners.append(ms)
        except Exception as exc:
            self.error = f"écoute globale impossible : {exc}"
            log.warning(self.error)
            return False
        return True

    def stop(self) -> None:
        for listener in self._listeners:
            listener.stop()
        self._listeners.clear()
