"""Pages de la fenêtre principale, une par entrée du menu latéral d'origine.

Ce module regroupe la base commune : classe ``Page``, champs de raccourci,
variables Tk liées à la configuration et libellés des actions.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable

from ... import i18n
from ...hotkeys import ACTION_LABELS_FR, Action, HotKey
from .. import theme as T
from .. import widgets as W

if TYPE_CHECKING:
    from ..app import App

tr = i18n.tr

# Index des libellés « HOTKEY_Friendly_Name_N » (énumération AppHotKeyName d'origine).
_FRIENDLY = {
    Action.SwitchLayout: 0, Action.ReorderPlayingArea: 1, Action.ReorderObserverArea: 2,
    Action.SendTableToPlayingArea: 3, Action.SendTableToObserverArea: 4, Action.PeekActiveLayoutHotKey: 5,
    Action.RNGMoveToPointer: 6, Action.CycleHoveredStack: 7, Action.Fold: 8, Action.Check: 9, Action.BetRaise: 10,
    Action.Button1: 11, Action.Button2: 12, Action.Button3: 13, Action.Button4: 14, Action.AllIn: 15,
    Action.DecreaseBet: 16, Action.IncreaseBet: 17, Action.BringNextTableToForeground: 18,
    Action.BringPreviousTableToForeground: 19, Action.MoveTableToNextSlot: 20, Action.MoveTableToPreviousSlot: 21,
    Action.MoveTableToNextSlotWithSwapping: 22, Action.MoveTableToPreviousSlotWithSwapping: 23,
    Action.FocusMostUrgentTable: 24, Action.OpenMenu: 25, Action.DisableAllHotkeys: 26, Action.ToggleBBMode: 28,
    Action.Button5: 29, Action.Button6: 30, Action.Button7: 31, Action.Button8: 32, Action.MinimizeTable: 34,
    Action.CloseTable: 35, Action.LockTableFromDynamicFlow: 55,
    **{Action(f"SendTableToPlayingSlot{i}"): 44 + i for i in range(1, 6)},
    **{Action(f"SendTableToObserverSlot{i}"): 49 + i for i in range(1, 6)},
    **{Action(f"Button{i}"): 47 + i for i in range(9, 17)},
}
_OTHER_KEYS = {
    Action.Increment: "HOTKEYS_NL_Label_Increment", Action.Decrement: "HOTKEYS_NL_Label_Decrement",
    Action.SitoutNextHand: "SETTINGS_NL_Label_Sitout_Next_Hand", Action.SitoutNextBB: "SETTINGS_NL_Label_Sitout_Next_BB",
    Action.SitBackIn: "SETTINGS_NL_Label_Sit_Back_Into_The_Table",
    Action.SitOutAtAllTables: "SETTINGS_NL_Label_Sit_Out_At_All_Tables",
}


def action_label(action: Action) -> str:
    idx = _FRIENDLY.get(action)
    if idx is not None and i18n.has(f"HOTKEY_Friendly_Name_{idx}"):
        return tr(f"HOTKEY_Friendly_Name_{idx}")
    key = _OTHER_KEYS.get(action)
    if key and i18n.has(key):
        return tr(key)
    return ACTION_LABELS_FR.get(action, action.value)


_KEY_TEXT = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Cmd", "wheel_up": "Wheel ↑",
             "wheel_down": "Wheel ↓", "mouse_left": "Mouse L", "mouse_right": "Mouse R",
             "mouse_middle": "Mouse M", "mouse4": "Mouse 4", "mouse5": "Mouse 5", "page_up": "PgUp",
             "page_down": "PgDn", "escape": "Esc", "space": "Space", "enter": "Enter"}


def format_hotkey(hk: HotKey | str | None) -> str:
    if not hk:
        return "—"
    hk = HotKey.parse(hk) if isinstance(hk, str) else hk
    parts = str(hk).split("+")
    return " + ".join(_KEY_TEXT.get(p, p.upper() if len(p) <= 3 else p.capitalize()) for p in parts)


class HotkeyField(tk.Label):
    """Case de raccourci : un clic ouvre « Définir le raccourci », clic droit = effacer."""

    def __init__(self, master, app: "App", get: Callable[[], HotKey | str | None],
                 set_: Callable[[HotKey | None], bool], bg: str = T.WINDOW_BG, width: int = 16, title: str = ""):
        super().__init__(master, bg=T.GRAY[100], fg=T.PRIMARY[800], font=T.font(9, "bold"), width=width, padx=8,
                         pady=6, cursor="hand2", highlightthickness=1, highlightbackground=T.GRAY[300])
        self.app, self.get, self.set_, self.title = app, get, set_, title
        self.bind("<Button-1>", lambda e: self._edit())
        self.bind("<Button-3>", lambda e: self._apply(None))
        self.bind("<Enter>", lambda e: self.configure(highlightbackground=T.ACCENT))
        self.bind("<Leave>", lambda e: self.configure(highlightbackground=T.GRAY[300]))
        self.refresh()

    def refresh(self):
        try:
            self.configure(text=format_hotkey(self.get()))
        except ValueError:
            self.configure(text="—")

    def _edit(self):
        self.app.capture_hotkey(self.title, self.get(), self._apply)

    def _apply(self, hk: HotKey | None):
        if self.set_(hk):
            self.refresh()


def action_field(master, app: "App", action: Action, bg: str = T.WINDOW_BG, width: int = 16) -> HotkeyField:
    def get():
        b = app.config.hotkeys.bindings.get(action)
        return b.hotkey if b else None
    return HotkeyField(master, app, get, lambda hk: app.bind_action(action, hk), bg, width, action_label(action))


def slot_labels() -> dict:
    from ...layout import SlotKind
    return {SlotKind.PLAYING: tr("LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Playing_Slot"),
            SlotKind.OBSERVER: tr("LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Observer_Slot"),
            SlotKind.ACTION_REQUIRED: tr("SITE_CONFIGURATION_DETAILS_NL_Label_Action_Required"),
            SlotKind.QUEUE: "Queue", SlotKind.IN_HAND: "In Hand", SlotKind.REPLAY: "Replay", SlotKind.LOBBY: "Lobby"}


def radio_group(master, var: tk.Variable, options: list[tuple[object, str]], bg: str = T.WINDOW_BG,
                vertical: bool = True, command: Callable | None = None) -> tk.Frame:
    f = tk.Frame(master, bg=bg)
    for value, text in options:
        rb = tk.Radiobutton(f, text=text, variable=var, value=value, bg=bg, fg=T.TEXT, activebackground=bg,
                            selectcolor=T.WINDOW_BG, font=T.font(10), anchor="w", highlightthickness=0,
                            command=command, cursor="hand2")
        rb.pack(anchor="w" if vertical else None, side="top" if vertical else "left", padx=(0, 0 if vertical else 16),
                pady=1)
    return f


class Page(tk.Frame):
    """Page affichée dans la zone de contenu ; construite au premier affichage."""

    title_key = ""
    icon: str | None = None

    def __init__(self, app: "App"):
        super().__init__(app.content, bg=T.WINDOW_BG)
        self.app = app
        self.cfg = app.config
        self.built = False
        self._vars: list[tk.Variable] = []

    # ------------------------------------------------------------------ cycle de vie
    def show(self):
        if not self.built:
            self.build()
            self.built = True
        self.refresh()

    def hide(self):
        pass

    def build(self):
        raise NotImplementedError

    def refresh(self):
        pass

    def refresh_live(self):
        """Appelé quand l'état des tables change (pages qui l'affichent)."""

    # ------------------------------------------------------------------ éléments communs
    def header(self, title: str, save: Callable | None = None, icon: str | None = None,
               save_text: str | None = None) -> tk.Frame:
        bar = tk.Frame(self, bg=T.WINDOW_BG)
        bar.pack(fill="x", padx=28, pady=(20, 8))
        W.page_title(bar, title, icon=icon or self.icon).pack(side="left")
        if save:
            W.RoundButton(bar, save_text or tr("SETTINGS_NL_Button_Save_Changes"), save).pack(side="right")
        return bar

    def tabs(self, parent, titles: list[str], builders: list[Callable[[tk.Frame], None]],
             scroll: bool = True) -> W.TabBar:
        """Onglets à soulignement ; chaque contenu est construit à sa première sélection."""
        holder = tk.Frame(parent, bg=T.WINDOW_BG)
        frames: list[tk.Widget | None] = [None] * len(titles)

        def select(i):
            for f in frames:
                if f is not None:
                    f.pack_forget()
            if frames[i] is None:
                if scroll:
                    sf = W.ScrollFrame(holder)
                    builders[i](sf.inner)
                    frames[i] = sf
                else:
                    fr = tk.Frame(holder, bg=T.WINDOW_BG)
                    builders[i](fr)
                    frames[i] = fr
            frames[i].pack(fill="both", expand=True)
            self.on_tab(i)

        bar = W.TabBar(parent, titles, select)
        bar.pack(fill="x", padx=28)
        tk.Frame(parent, bg=T.BORDER, height=1).pack(fill="x", padx=28)
        holder.pack(fill="both", expand=True, padx=(28, 8), pady=(10, 0))
        bar.frames = frames
        return bar

    def on_tab(self, index: int):
        pass

    def var(self, obj, attr: str, kind: type = bool, on_change: Callable | None = None) -> tk.Variable:
        """Variable Tk liée à ``obj.attr`` : toute modification s'applique et est enregistrée."""
        cls = {bool: tk.BooleanVar, int: tk.IntVar, float: tk.DoubleVar, str: tk.StringVar}[kind]
        v = cls(value=getattr(obj, attr))

        def write(*_):
            try:
                value = kind(v.get())
            except (tk.TclError, ValueError):
                return
            if getattr(obj, attr) != value:
                setattr(obj, attr, value)
                if on_change:
                    on_change()
                self.app.changed()
        v.trace_add("write", write)
        self._vars.append(v)
        return v

    def keep(self, v: tk.Variable) -> tk.Variable:
        self._vars.append(v)
        return v

    def row(self, parent, icon: str | None, title_key: str, obj, attr: str, tip_key: str | None = None,
            subtitle: str = "", on_change: Callable | None = None, enabled: bool = True) -> W.SettingRow:
        """Ligne de réglage avec interrupteur, au texte d'origine (clé + info-bulle)."""
        tip = (tr(title_key), tr(tip_key)) if tip_key and i18n.has(tip_key) else None
        r = W.SettingRow(parent, icon, tr(title_key), self.var(obj, attr, bool, on_change), tooltip=tip,
                         subtitle=subtitle, enabled=enabled)
        r.pack(fill="x", padx=(0, 12))
        return r

    def separator(self, parent):
        tk.Frame(parent, bg=T.BORDER, height=1).pack(fill="x", pady=8, padx=(0, 12))


def spin(master, var: tk.Variable, from_: float, to: float, increment: float = 1, width: int = 6) -> ttk.Spinbox:
    return ttk.Spinbox(master, textvariable=var, from_=from_, to=to, increment=increment, width=width)


def combo(master, var: tk.Variable, values: list[str], width: int = 22) -> ttk.Combobox:
    return ttk.Combobox(master, textvariable=var, values=values, state="readonly", width=width)


def bold(master, text: str, bg: str = T.WINDOW_BG, size: int = 10, fg: str = T.TEXT) -> tk.Label:
    return tk.Label(master, text=text, bg=bg, fg=fg, font=T.font(size, "bold"), anchor="w", justify="left")


def own(fr: str, en: str) -> str:
    """Texte propre à Fukuroku (absent des fichiers de langue d'origine)."""
    return fr if i18n.language() == "fr" else en


NOT_PORTED = ("Fonction de l'original qui s'injecte dans le client de poker (DLL) : non portée, Fukuroku ne modifie "
              "pas les clients et ne lit pas leur mémoire.",
              "Original feature that injects a DLL into the poker client: not ported, Fukuroku never modifies "
              "clients nor reads their memory.")
NEEDS_DATA = ("Nécessite un fournisseur de données de table (pot, mises, cartes) branché sur "
              "TableManager.data_provider.",
              "Requires a table data provider (pot, bets, cards) plugged into TableManager.data_provider.")
