"""Backend simulé : fenêtres virtuelles en mémoire (tests, démonstration)."""

from __future__ import annotations

from ..geometry import Rect
from .base import Backend, WindowInfo


class DummyBackend(Backend):
    name = "simulation"
    capabilities = {"windows", "move", "click", "keys"}

    def __init__(self, screens: list[Rect] | None = None):
        self._screens = screens or [Rect(0, 0, 1920, 1080)]
        self.windows: dict[int, WindowInfo] = {}
        self.z_order: list[int] = []
        self.cursor = (0, 0)
        self.log: list[tuple] = []
        self._next = 1
        self.pixels: dict[tuple[int, int], tuple[int, int, int]] = {}

    def add_window(self, title: str, process: str, rect: Rect, class_name: str = "") -> int:
        h = self._next
        self._next += 1
        self.windows[h] = WindowInfo(h, title, process, rect, class_name=class_name)
        self.z_order.insert(0, h)
        return h

    def remove_window(self, handle: int) -> None:
        self.windows.pop(handle, None)
        if handle in self.z_order:
            self.z_order.remove(handle)

    def list_windows(self):
        return [self.windows[h] for h in self.z_order if h in self.windows]

    def move_resize(self, handle, rect):
        if handle in self.windows:
            self.windows[handle].rect = rect
        self.log.append(("move", handle, rect))

    def bring_to_front(self, handle):
        if handle in self.z_order:
            self.z_order.remove(handle)
            self.z_order.insert(0, handle)
        self.log.append(("raise", handle))

    def focus(self, handle):
        self.bring_to_front(handle)
        self.log.append(("focus", handle))

    def minimize(self, handle):
        if handle in self.windows:
            self.windows[handle].minimized = True
        self.log.append(("minimize", handle))

    def close(self, handle):
        self.remove_window(handle)
        self.log.append(("close", handle))

    def screens(self):
        return list(self._screens)

    def cursor_pos(self):
        return self.cursor

    def set_cursor_pos(self, x, y):
        self.cursor = (x, y)

    def click(self, x, y, button="left", restore_cursor=True):
        self.log.append(("click", x, y, button))

    def type_text(self, text):
        self.log.append(("type", text))

    def key_combo(self, combo):
        self.log.append(("key", combo))

    def pixel(self, x, y):
        return self.pixels.get((x, y))

    def foreground(self):
        return self.z_order[0] if self.z_order else None
