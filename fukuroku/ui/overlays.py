"""Fenêtres flottantes : RNG, minuteur de session, compteurs (AR, ST, mains),
aperçu du layout actif, bordures « action requise » et overlays de table."""

from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from typing import Callable

from .. import rng
from ..geometry import Rect
from ..layout import SLOT_COLORS, Layout, SlotKind
from . import theme as T

TRANSPARENT = "#010203"  # couleur rendue transparente (Windows) pour les formes arrondies


def _transparent(win: tk.Toplevel, bg: str) -> str:
    """Fond transparent si la plateforme le permet, sinon fond sombre."""
    try:
        win.attributes("-transparentcolor", TRANSPARENT)
        return TRANSPARENT
    except tk.TclError:
        return bg


class FloatingWindow(tk.Toplevel):
    """Fenêtre sans bordure, toujours au premier plan, déplaçable à la souris."""

    def __init__(self, master, alpha: float = 0.95, bg: str = T.DARK, on_moved: Callable | None = None):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        self.configure(bg=bg)
        self._drag = (0, 0)
        self._on_moved = on_moved
        self.bind_drag(self)

    def bind_drag(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._on_drag, add="+")
        widget.bind("<ButtonRelease-1>", lambda e: self._on_moved and self._on_moved(self.winfo_x(), self.winfo_y()),
                    add="+")

    def _start_drag(self, e):
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _on_drag(self, e):
        self.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def place_at(self, pos):
        if pos:
            self.geometry(f"+{int(pos[0])}+{int(pos[1])}")


class RngOverlay(FloatingWindow):
    """RNG d'origine : jeton violet avec afficheur digital (RandomNumberWindow)."""

    SIZE = 128

    def __init__(self, master, settings: rng.RngSettings, on_moved: Callable | None = None):
        super().__init__(master, settings.opacity, T.DARK, on_moved=lambda x, y: self._moved(x, y))
        self.settings = settings
        self._user_moved = on_moved
        bg = _transparent(self, T.DARK)
        self.configure(bg=bg)
        self.canvas = tk.Canvas(self, width=self.SIZE, height=self.SIZE, bg=bg, highlightthickness=0, cursor="fleur")
        self.canvas.pack()
        chip = T.image("configuration/show_rng.png", self.SIZE)
        if chip:
            self.canvas.create_image(self.SIZE // 2, self.SIZE // 2, image=chip)
        else:
            self.canvas.create_oval(4, 4, self.SIZE - 4, self.SIZE - 4, fill=T.ACCENT, outline="")
        # Masque de l'afficheur du jeton, puis valeur en police digitale.
        self.canvas.create_rectangle(36, 50, 92, 74, fill="#1B185A", outline="")
        self.text = self.canvas.create_text(self.SIZE // 2, 62, text="--", fill="white", font=T.digital(22))
        self.bind_drag(self.canvas)
        self.canvas.bind("<Button-3>", lambda e: self.roll())
        self.canvas.bind("<Double-Button-1>", lambda e: self.roll())
        self.place_at(settings.position or (100, 100))
        self._job = None
        self.roll()

    def _moved(self, x, y):
        self.settings.position = (x, y)
        if self._user_moved:
            self._user_moved(x, y)

    def roll(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        value = rng.draw(self.settings.minimum, self.settings.maximum)
        self.canvas.itemconfigure(self.text, text=str(value), fill=rng.color_for(value, self.settings))
        if self.settings.roll_on == "time":
            self._job = self.after(int(max(0.5, self.settings.interval_s) * 1000), self.roll)

    def move_to(self, x: int, y: int):
        self.geometry(f"+{x - self.SIZE // 2}+{y - self.SIZE // 2}")
        self._moved(x - self.SIZE // 2, y - self.SIZE // 2)


class SessionTimerWidget(FloatingWindow):
    """Minuteur de session (SessionTimeWindow : 207 × 80, bandeau dégradé, durée)."""

    def __init__(self, master, elapsed: Callable[[], str], running: Callable[[], bool],
                 on_start: Callable, on_stop: Callable, on_moved: Callable | None = None, position=None):
        super().__init__(master, 0.97, T.DARK, on_moved)
        self.elapsed, self.running = elapsed, running
        self.minimized = False
        self.body = tk.Frame(self, bg=T.DARK, padx=10, pady=8)
        self.body.pack()
        head = tk.Frame(self.body, bg=T.DARK)
        head.pack(fill="x")
        icon = T.image("session/widget.png", 22)
        tk.Label(head, image=icon, bg=T.DARK).pack(side="left")
        tk.Label(head, text="Session", bg=T.DARK, fg=T.PRIMARY[200], font=T.font(9, "bold")).pack(side="left", padx=6)
        mini = tk.Label(head, text="–", bg=T.DARK, fg=T.GRAY[400], font=T.font(10, "bold"), cursor="hand2")
        mini.pack(side="right")
        mini.bind("<Button-1>", lambda e: self.toggle_minimized())
        self.row = tk.Frame(self.body, bg=T.DARK)
        self.row.pack(fill="x", pady=(6, 0))
        box = tk.Frame(self.row, bg="white", padx=8, pady=2)
        box.pack(side="left")
        self.time = tk.Label(box, text="00:00:00", bg="white", fg="black", font=T.digital(20))
        self.time.pack()
        self.play = tk.Label(self.row, bg=T.DARK, cursor="hand2")
        self.play.pack(side="left", padx=(10, 0))
        self.play.bind("<Button-1>", lambda e: (on_stop() if self.running() else on_start()))
        for w in (self.body, head, self.row, box, self.time):
            self.bind_drag(w)
        self.place_at(position or (20, 20))
        self._tick()

    def toggle_minimized(self):
        self.minimized = not self.minimized
        if self.minimized:
            self.row.pack_forget()
        else:
            self.row.pack(fill="x", pady=(6, 0))

    def _tick(self):
        try:
            self.time.configure(text=self.elapsed())
            img = T.image("session/stop_session.png" if self.running() else "session/manually_use_widget.png", 30)
            self.play.configure(image=img)
            self.play.image = img
        except tk.TclError:
            return
        self.after(500, self._tick)


class CounterWidget(FloatingWindow):
    """Compteur flottant (tables AR, tables empilées, mains, tables ouvertes)."""

    def __init__(self, master, icon: str, provider: Callable[[], int | str], on_moved: Callable | None = None,
                 position=None, tooltip: str = ""):
        super().__init__(master, 0.95, "#22242A", on_moved)
        f = tk.Frame(self, bg="#22242A", padx=8, pady=4)
        f.pack()
        img = T.image(icon, 28)
        il = tk.Label(f, image=img, bg="#22242A")
        il.pack(side="left")
        self.value = tk.Label(f, text="0", bg="#22242A", fg="white", font=T.digital(22), width=3)
        self.value.pack(side="left", padx=(6, 0))
        for w in (f, il, self.value):
            self.bind_drag(w)
        self.provider = provider
        self.place_at(position or (20, 120))
        self._tick()

    def _tick(self):
        try:
            v = self.provider()
            self.value.configure(text=f"{v:02d}" if isinstance(v, int) else str(v))
        except tk.TclError:
            return
        except Exception:
            pass
        self.after(400, self._tick)


class LayoutPeek:
    """Aperçu des slots du layout actif (PeekActiveLayout / LayoutPreviewWindow)."""

    def __init__(self, master, layout: Layout, labels: dict[SlotKind, str], duration_ms: int = 1500):
        self.windows = []
        for slot in layout.slots:
            color = SLOT_COLORS[slot.kind]
            w = tk.Toplevel(master)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            try:
                w.attributes("-alpha", 0.45)
            except tk.TclError:
                pass
            r = slot.rect
            w.geometry(f"{max(40, r.w)}x{max(30, r.h)}+{r.x}+{r.y}")
            w.configure(bg=color, highlightthickness=3, highlightbackground="white")
            tk.Label(w, text=f"{labels.get(slot.kind, slot.kind.value)}\n{layout.number_of(slot)}",
                     font=T.font(22, "bold"), fg="white", bg=color).place(relx=.5, rely=.5, anchor="center")
            self.windows.append(w)
        master.after(duration_ms, self.close)

    def close(self):
        for w in self.windows:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.windows.clear()


def _mix(c1: str, c2: str, k: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * max(0.0, min(1.0, k))) for x, y in zip(a, b))


def border_color(elapsed: float, settings) -> str:
    """Couleur de la bordure selon le temps écoulé depuis le début du tour."""
    remaining = settings.turn_seconds - elapsed
    if settings.mode == "colors":
        return settings.color_end if remaining <= settings.last_seconds else settings.color_start
    k = elapsed / max(1, settings.turn_seconds)  # vert → jaune → rouge
    return _mix(T.GREEN[400], T.YELLOW[300], k * 2) if k < 0.5 else _mix(T.YELLOW[300], T.RED[500], (k - 0.5) * 2)


class TableBorders:
    """Bordures autour des tables (« Afficher la bordure quand c'est votre tour »)."""

    def __init__(self, master):
        self.master = master
        self.frames: dict[object, list[tk.Toplevel]] = {}

    def _make(self) -> list[tk.Toplevel]:
        out = []
        for _ in range(4):
            w = tk.Toplevel(self.master)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            try:
                w.attributes("-disabled", True)
            except tk.TclError:
                pass
            out.append(w)
        return out

    def update(self, items: dict[object, tuple[Rect, str]], size: int, blink_off: bool = False) -> None:
        for handle in [h for h in self.frames if h not in items]:
            for w in self.frames.pop(handle):
                w.destroy()
        for handle, (r, color) in items.items():
            wins = self.frames.get(handle) or self._make()
            self.frames[handle] = wins
            s = max(1, size)
            geoms = [(r.w + 2 * s, s, r.x - s, r.y - s), (r.w + 2 * s, s, r.x - s, r.bottom),
                     (s, r.h, r.x - s, r.y), (s, r.h, r.right, r.y)]
            for w, (gw, gh, gx, gy) in zip(wins, geoms):
                w.geometry(f"{gw}x{gh}+{gx}+{gy}")
                w.configure(bg=color)
                if blink_off:
                    w.withdraw()
                else:
                    w.deiconify()
                    w.lift()

    def clear(self):
        self.update({}, 1)


class TableOverlay:
    """Overlays attachés à une table : boutons de mise, capture d'écran, textes de données."""

    def __init__(self, master, handle, on_bet: Callable[[object, int], None], on_screenshot: Callable[[object], None]):
        self.handle = handle
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        self.win.configure(bg=T.DARK)
        self.bar = tk.Frame(self.win, bg=T.DARK, padx=3, pady=3)
        self.bar.pack(side="left")
        self.data = tk.Label(self.win, text="", bg=T.DARK, fg="white", font=T.font(9, "bold"), padx=6)
        self.on_bet, self.on_screenshot = on_bet, on_screenshot
        self._signature = None

    def update(self, rect: Rect, labels: list[str], screenshot: bool, data_text: str, visible: bool):
        signature = (tuple(labels), screenshot)
        if signature != self._signature:
            self._signature = signature
            for child in self.bar.winfo_children():
                child.destroy()
            for i, text in enumerate(labels, start=1):
                b = tk.Label(self.bar, text=text, bg=T.ACCENT, fg="white", font=T.font(8, "bold"), padx=6, pady=2,
                             cursor="hand2")
                b.pack(side="left", padx=1)
                b.bind("<Button-1>", lambda e, i=i: self.on_bet(self.handle, i))
            if screenshot:
                cam = tk.Label(self.bar, text="📷", bg=T.GRAY[700], fg="white", padx=5, cursor="hand2")
                cam.pack(side="left", padx=(4, 0))
                cam.bind("<Button-1>", lambda e: self.on_screenshot(self.handle))
        if data_text:
            self.data.configure(text=data_text)
            self.data.pack(side="left")
        else:
            self.data.pack_forget()
        if not visible or (not labels and not screenshot and not data_text):
            self.win.withdraw()
            return
        self.win.deiconify()
        self.win.update_idletasks()
        x = rect.x + max(0, (rect.w - self.win.winfo_reqwidth()) // 2)
        y = rect.bottom - self.win.winfo_reqheight() - max(4, rect.h // 5)
        self.win.geometry(f"+{x}+{y}")

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def screenshot(rect: Rect, folder: Path) -> Path | None:
    """Capture d'écran d'une table (overlay « Prendre une capture d'écran »)."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("table-%Y%m%d-%H%M%S.png")
    ImageGrab.grab(bbox=(rect.x, rect.y, rect.right, rect.bottom), all_screens=True).save(path)
    return path
