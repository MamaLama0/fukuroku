"""Contrôles au style du logiciel d'origine : interrupteurs, boutons arrondis,
cartes, lignes de réglage avec icône, info-bulles, onglets, dialogues, toasts."""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font  # noqa: F401  (tk.font)
from tkinter import ttk
from typing import Callable

from . import theme as T


def _rounded(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2,
           x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class ToggleSwitch(tk.Canvas):
    """Interrupteur (style « Switch » de l'original)."""

    W, H = 42, 22

    def __init__(self, master, variable: tk.BooleanVar, command: Callable | None = None, bg: str = T.WINDOW_BG):
        super().__init__(master, width=self.W, height=self.H, bg=bg, highlightthickness=0, cursor="hand2")
        self.var, self.command = variable, command
        self.bind("<Button-1>", self._toggle)
        variable.trace_add("write", lambda *a: self._draw())
        self._draw()

    def _toggle(self, _e=None):
        if str(self.cget("state")) == "disabled":
            return
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def _draw(self):
        self.delete("all")
        on = bool(self.var.get())
        _rounded(self, 1, 1, self.W - 1, self.H - 1, 11, fill=T.ACCENT if on else T.GRAY[300], outline="")
        x = self.W - 12 if on else 12
        self.create_oval(x - 8, 3, x + 8, self.H - 3, fill="white", outline="")


class RoundButton(tk.Canvas):
    """Bouton arrondi (AppButtonStyle : primaire violet, secondaire, danger, discret)."""

    STYLES = {
        "primary": (T.ACCENT, T.PRIMARY[600], "white"),
        "secondary": (T.PRIMARY[50], T.PRIMARY[100], T.PRIMARY[700]),
        "danger": (T.RED[500], T.RED[600], "white"),
        "success": (T.GREEN[400], T.GREEN[500], "white"),
        "dark": (T.DARK, T.PRIMARY[800], "white"),
        "ghost": (T.WINDOW_BG, T.GRAY[100], T.TEXT),
    }

    def __init__(self, master, text: str, command: Callable | None = None, kind: str = "primary",
                 icon: str | None = None, width: int | None = None, height: int = 36, bg: str | None = None,
                 font_size: int = 10):
        self.text, self.command, self.kind = text, command, kind
        self.icon = T.image(icon, 20) if icon else None
        f = T.font(font_size, "bold")
        measure = tk.font.Font(font=f).measure(text) if text else 0
        width = width or measure + 36 + (26 if self.icon else 0)
        super().__init__(master, width=width, height=height, highlightthickness=0, cursor="hand2",
                         bg=bg or self._parent_bg(master))
        self._bw, self._bh, self._font = width, height, f
        self._hover = False
        self._enabled = True
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._click)
        self._draw()

    @staticmethod
    def _parent_bg(master) -> str:
        try:
            return master.cget("bg")
        except tk.TclError:
            return T.WINDOW_BG

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text: str):
        self.text = text
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def _click(self, _e):
        if self._enabled and self.command:
            self.command()

    def _draw(self):
        self.delete("all")
        base, hover, fg = self.STYLES.get(self.kind, self.STYLES["primary"])
        if not self._enabled:
            base, hover, fg = T.GRAY[200], T.GRAY[200], T.GRAY[500]
        border = T.GRAY[300] if self.kind == "ghost" else ""
        _rounded(self, 1, 1, self._bw - 1, self._bh - 1, 8, fill=hover if self._hover else base, outline=border)
        x = self._bw / 2
        if self.icon:
            tw = tk.font.Font(font=self._font).measure(self.text)
            x0 = (self._bw - tw - 26) / 2
            self.create_image(x0 + 10, self._bh / 2, image=self.icon)
            x = x0 + 26 + tw / 2
        self.create_text(x, self._bh / 2, text=self.text, fill=fg, font=self._font)


class Card(tk.Frame):
    def __init__(self, master, padding: int = 14, bg: str = T.WINDOW_BG, **kw):
        super().__init__(master, bg=bg, highlightthickness=1, highlightbackground=T.BORDER, padx=padding,
                         pady=padding, **kw)


class Tooltip:
    """Info-bulle sombre avec titre (AppTooltip / FeatureTooltip de l'original)."""

    def __init__(self, widget: tk.Widget, title: str, body: str = "", image: str | None = None):
        self.widget, self.title, self.body, self.image = widget, title, body, image
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _e=None):
        if self.tip or not (self.title or self.body):
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
        y = self.widget.winfo_rooty() - 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        frame = tk.Frame(tw, bg=T.DARK, padx=14, pady=10)
        frame.pack()
        img = T.image(self.image, 64) if self.image else None
        if img:
            tk.Label(frame, image=img, bg=T.DARK).pack(anchor="w", pady=(0, 6))
        if self.title:
            tk.Label(frame, text=self.title, bg=T.DARK, fg="white", font=T.font(10, "bold"), justify="left",
                     wraplength=320).pack(anchor="w")
        if self.body:
            tk.Label(frame, text=strip_html(self.body), bg=T.DARK, fg=T.GRAY[300], font=T.font(9), justify="left",
                     wraplength=320).pack(anchor="w", pady=(4, 0))
        tw.update_idletasks()
        sw = tw.winfo_screenwidth()
        if x + tw.winfo_width() > sw:
            x = self.widget.winfo_rootx() - tw.winfo_width() - 8
        tw.geometry(f"+{x}+{y}")

    def hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def strip_html(text: str) -> str:
    text = re.sub(r"</p>\s*<p>|<br\s*/?>", "\n", text or "")
    return re.sub(r"<[^>]+>", "", text).strip()


def help_icon(master, title: str, body: str, bg: str = T.WINDOW_BG) -> tk.Label:
    lbl = tk.Label(master, text="?", bg=T.PRIMARY[100], fg=T.PRIMARY[700], font=T.font(8, "bold"), width=2,
                   cursor="question_arrow")
    Tooltip(lbl, title, body)
    return lbl


class SettingRow(tk.Frame):
    """Ligne de réglage de l'original : icône illustrée, libellé, aide, interrupteur."""

    def __init__(self, master, icon: str | None, title: str, variable: tk.Variable | None = None,
                 tooltip: tuple[str, str] | None = None, command: Callable | None = None,
                 control: Callable[[tk.Widget], tk.Widget] | None = None, bg: str = T.WINDOW_BG,
                 subtitle: str = "", enabled: bool = True):
        super().__init__(master, bg=bg, pady=6)
        img = T.image(icon, 40) if icon else None
        if img:
            tk.Label(self, image=img, bg=bg, width=48).pack(side="left")
        text = tk.Frame(self, bg=bg)
        text.pack(side="left", fill="x", expand=True, padx=(8, 4))
        top = tk.Frame(text, bg=bg)
        top.pack(anchor="w")
        tk.Label(top, text=title, bg=bg, fg=T.TEXT if enabled else T.GRAY[500], font=T.font(10, "bold"),
                 justify="left", wraplength=520, anchor="w").pack(side="left")
        if tooltip and (tooltip[0] or tooltip[1]):
            help_icon(top, *tooltip, bg=bg).pack(side="left", padx=6)
        if subtitle:
            tk.Label(text, text=subtitle, bg=bg, fg=T.TEXT_MUTED, font=T.font(9), justify="left", wraplength=560,
                     anchor="w").pack(anchor="w")
        if control is not None:
            control(self).pack(side="right", padx=4)
        elif variable is not None:
            sw = ToggleSwitch(self, variable, command, bg=bg)
            if not enabled:
                sw.configure(state="disabled")
            sw.pack(side="right", padx=4)


class TabBar(tk.Frame):
    """Onglets à soulignement violet (HeaderedTabControl)."""

    def __init__(self, master, tabs: list[str], on_select: Callable[[int], None], bg: str = T.WINDOW_BG):
        super().__init__(master, bg=bg)
        self.on_select = on_select
        self.labels: list[tk.Label] = []
        self.bars: list[tk.Frame] = []
        for i, title in enumerate(tabs):
            col = tk.Frame(self, bg=bg)
            col.pack(side="left", padx=(0, 22))
            lbl = tk.Label(col, text=title, bg=bg, font=T.font(10, "bold"), cursor="hand2", pady=6)
            lbl.pack()
            bar = tk.Frame(col, height=3, bg=bg)
            bar.pack(fill="x")
            lbl.bind("<Button-1>", lambda e, i=i: self.select(i))
            self.labels.append(lbl)
            self.bars.append(bar)
        self.current = -1

    def select(self, index: int):
        self.current = index
        for i, (lbl, bar) in enumerate(zip(self.labels, self.bars)):
            lbl.configure(fg=T.ACCENT if i == index else T.TEXT_MUTED)
            bar.configure(bg=T.ACCENT if i == index else self.cget("bg"))
        self.on_select(index)


class ScrollFrame(tk.Frame):
    """Zone défilante verticale ; le contenu va dans ``self.inner``."""

    def __init__(self, master, bg: str = T.WINDOW_BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind_all_wheel(self.inner)

    def bind_all_wheel(self, widget):
        widget.bind("<Enter>", lambda e: self._wheel(True), add="+")
        widget.bind("<Leave>", lambda e: self._wheel(False), add="+")

    def _wheel(self, on: bool):
        if on:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
            self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
            self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
        else:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, e):
        delta = e.delta if abs(e.delta) < 120 else e.delta // 120
        self.canvas.yview_scroll(-delta * (1 if abs(e.delta) < 120 else 2), "units")


def page_title(master, text: str, bg: str = T.WINDOW_BG, icon: str | None = None) -> tk.Frame:
    f = tk.Frame(master, bg=bg)
    img = T.image(icon, 36) if icon else None
    if img:
        tk.Label(f, image=img, bg=bg).pack(side="left", padx=(0, 10))
    tk.Label(f, text=text, bg=bg, fg=T.PRIMARY[900], font=T.font(18, "bold")).pack(side="left")
    return f


def section(master, text: str, bg: str = T.WINDOW_BG) -> tk.Label:
    return tk.Label(master, text=text, bg=bg, fg=T.PRIMARY[700], font=T.font(11, "bold"), anchor="w")


def label(master, text: str, bg: str = T.WINDOW_BG, muted: bool = False, size: int = 10, bold: bool = False,
          wrap: int = 0) -> tk.Label:
    return tk.Label(master, text=text, bg=bg, fg=T.TEXT_MUTED if muted else T.TEXT,
                    font=T.font(size, "bold" if bold else "normal"), justify="left", anchor="w", wraplength=wrap)


def banner(master, text: str, kind: str = "info", bg: str = T.WINDOW_BG) -> tk.Frame:
    """Bandeau d'information (bleu) ou d'avertissement (jaune)."""
    colors = {"info": (T.BLUE[50], T.BLUE[700]), "warning": (T.YELLOW[50], T.YELLOW[600]),
              "lock": (T.PRIMARY[50], T.PRIMARY[700])}
    back, fore = colors.get(kind, colors["info"])
    f = tk.Frame(master, bg=back, padx=12, pady=8)
    tk.Label(f, text=("ⓘ  " if kind != "warning" else "⚠  ") + text, bg=back, fg=fore, font=T.font(9, "bold"),
             justify="left", wraplength=760, anchor="w").pack(anchor="w")
    return f


class AppDialog(tk.Toplevel):
    """Dialogue modal au style AppDialogV2 (titre, image, message, boutons)."""

    def __init__(self, master, title: str, message: str = "", buttons: list[tuple[str, str, object]] | None = None,
                 image: str | None = None, body: Callable[[tk.Frame], None] | None = None, width: int = 420):
        super().__init__(master)
        self.result = None
        self.title(title)
        self.configure(bg=T.WINDOW_BG)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        frame = tk.Frame(self, bg=T.WINDOW_BG, padx=26, pady=20)
        frame.pack(fill="both", expand=True)
        img = T.image(image, 96) if image else None
        if img:
            tk.Label(frame, image=img, bg=T.WINDOW_BG).pack(pady=(0, 10))
        tk.Label(frame, text=title, bg=T.WINDOW_BG, fg=T.PRIMARY[900], font=T.font(14, "bold"),
                 wraplength=width).pack()
        if message:
            tk.Label(frame, text=strip_html(message), bg=T.WINDOW_BG, fg=T.TEXT_MUTED, font=T.font(10),
                     wraplength=width, justify="center").pack(pady=(8, 0))
        if body:
            content = tk.Frame(frame, bg=T.WINDOW_BG)
            content.pack(fill="both", expand=True, pady=(10, 0))
            body(content)
        row = tk.Frame(frame, bg=T.WINDOW_BG)
        row.pack(pady=(18, 0))
        for text, kind, value in buttons or [("OK", "primary", True)]:
            RoundButton(row, text, lambda v=value: self.close(v), kind=kind).pack(side="left", padx=6)
        self.bind("<Escape>", lambda e: self.close(None))
        self.update_idletasks()
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_width()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def close(self, value):
        self.result = value
        self.destroy()

    def wait(self):
        self.wait_window()
        return self.result


def ask_yes_no(master, title: str, message: str, yes: str, no: str, image: str | None = None,
               danger: bool = False) -> bool:
    return bool(AppDialog(master, title, message, [(no, "ghost", False), (yes, "danger" if danger else "primary", True)],
                          image).wait())


def info(master, title: str, message: str, ok: str = "OK", image: str | None = None) -> None:
    AppDialog(master, title, message, [(ok, "primary", True)], image).wait()


class Toast:
    """Notification en bas à droite de la fenêtre principale (Toastr)."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.win: tk.Toplevel | None = None
        self._job = None

    def show(self, text: str, image: str | None = None, ms: int = 3500):
        self.close()
        self.win = w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        f = tk.Frame(w, bg=T.DARK, padx=14, pady=10)
        f.pack()
        img = T.image(image, 36) if image else None
        if img:
            tk.Label(f, image=img, bg=T.DARK).pack(side="left", padx=(0, 10))
        tk.Label(f, text=text, bg=T.DARK, fg="white", font=T.font(10, "bold"), wraplength=320,
                 justify="left").pack(side="left")
        w.update_idletasks()
        try:
            x = self.root.winfo_rootx() + self.root.winfo_width() - w.winfo_width() - 16
            y = self.root.winfo_rooty() + self.root.winfo_height() - w.winfo_height() - 46
            if self.root.state() == "iconic" or self.root.winfo_rootx() < -1000:
                x = w.winfo_screenwidth() - w.winfo_width() - 20
                y = w.winfo_screenheight() - w.winfo_height() - 60
        except tk.TclError:
            x, y = 40, 40
        w.geometry(f"+{x}+{y}")
        self._job = self.root.after(ms, self.close)

    def close(self):
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None
        if self.win:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
