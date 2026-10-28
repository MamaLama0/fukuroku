"""Fenêtre principale au style du logiciel d'origine (AppWindowN).

Menu latéral violet repliable (60 / 194 px), zone de pages, barre d'état ;
gère aussi les raccourcis globaux, la manette, les sons d'alerte, les
widgets flottants (RNG, minuteur, compteurs), les bordures de table et les
overlays attachés aux tables.
"""

from __future__ import annotations

import logging
import queue
import sys
import time
import tkinter as tk
import webbrowser
from pathlib import Path

from .. import APP_NAME, REPO_URL, __version__, assets, i18n, pokermath, sounds
from ..backends import Backend
from ..config import Config, config_dir
from ..gamepad import GamepadListener
from ..hotkeys import Action, HotKey
from ..inputs import InputListener
from ..manager import TableManager
from ..session import SessionHistory
from . import theme as T
from . import widgets as W
from .overlays import (CounterWidget, LayoutPeek, RngOverlay, SessionTimerWidget, TableBorders, TableOverlay,
                       border_color, screenshot)
from .pages import action_label, format_hotkey, slot_labels, tr

log = logging.getLogger("fukuroku")

# (identifiant, glyphe, clé du titre d'origine)
MENU = [
    ("home", "⌂", "APP_HAMBURGER_MENU_ITEM_Title_Home"),
    ("layouts", "▦", "APP_HAMBURGER_MENU_ITEM_Title_Layout"),
    ("sites", "♠", "APP_HAMBURGER_MENU_ITEM_Title_Sites"),
    ("hotkeys", "⌨", "APP_HAMBURGER_MENU_ITEM_Title_HotKeys"),
    ("controller", "✜", "APP_HAMBURGER_MENU_ITEM_Title_Controller"),
    ("overlays", "◩", "APP_HAMBURGER_MENU_ITEM_Title_Overlays"),
    ("session", "◷", "APP_HAMBURGER_MENU_ITEM_Title_SessionTime"),
    ("settings", "⚙", "APP_HAMBURGER_MENU_ITEM_Title_Configuration"),
    ("help", "?", "APP_HAMBURGER_MENU_ITEM_Title_Help"),
    ("changelog", "★", "APP_HAMBURGER_MENU_ITEM_Title_Changelog"),
]

_TK_MODS = {"control_l": "ctrl", "control_r": "ctrl", "alt_l": "alt", "alt_r": "alt", "shift_l": "shift",
            "shift_r": "shift", "meta_l": "cmd", "meta_r": "cmd", "super_l": "cmd", "super_r": "cmd",
            "win_l": "cmd", "win_r": "cmd", "iso_level3_shift": "alt", "option_l": "alt", "option_r": "alt",
            "command": "cmd"}
_TK_KEYS = {"prior": "page_up", "next": "page_down", "return": "enter", "kp_enter": "enter",
            "escape": "escape", "backspace": "backspace", "caps_lock": "caps_lock"}


def _tk_key_name(e) -> str:
    """Nom de touche Tk → nom utilisé par pynput (inputs.key_to_name)."""
    if sys.platform == "win32":
        if 48 <= e.keycode <= 57 or 65 <= e.keycode <= 90:
            return chr(e.keycode).lower()
        if 96 <= e.keycode <= 105:
            return f"num{e.keycode - 96}"
    low = e.keysym.lower()
    if low.startswith("kp_") and low[3:].isdigit():
        return "num" + low[3:]
    if len(e.keysym) == 1:
        return e.keysym.lower()
    return _TK_KEYS.get(low, low)


class HotkeyDialog(tk.Toplevel):
    """« Définir le raccourci » : Entrée enregistre, Échap efface, fermer annule."""

    def __init__(self, app: "App", title: str, current, on_done):
        super().__init__(app.root)
        self.app, self.on_done = app, on_done
        self.hk = HotKey.parse(current) if isinstance(current, str) and current else current
        self.mods: set[str] = set()
        self._was_suspended = app.hotkeys_suspended
        app.hotkeys_suspended = True
        self.title(tr("DIALOG_SET_HOTKEY_Title"))
        self.configure(bg=T.WINDOW_BG)
        self.resizable(False, False)
        self.transient(app.root)
        f = tk.Frame(self, bg=T.WINDOW_BG, padx=28, pady=22)
        f.pack()
        tk.Label(f, image=T.image("hotkey/hotkey_binding_dialog.png", 90), bg=T.WINDOW_BG).pack()
        tk.Label(f, text=tr("DIALOG_SET_HOTKEY_Title"), bg=T.WINDOW_BG, fg=T.PRIMARY[900],
                 font=T.font(14, "bold")).pack(pady=(6, 0))
        if title:
            tk.Label(f, text=title, bg=T.WINDOW_BG, fg=T.TEXT_MUTED, font=T.font(10)).pack()
        self.display = tk.Label(f, text=format_hotkey(self.hk), bg=T.PRIMARY[50], fg=T.PRIMARY[800], width=26,
                                font=T.font(16, "bold"), pady=16, highlightthickness=2,
                                highlightbackground=T.ACCENT, cursor="crosshair")
        self.display.pack(pady=12, fill="x")
        self.error = tk.Label(f, text="", bg=T.WINDOW_BG, fg=T.RED[500], font=T.font(9, "bold"), wraplength=380)
        self.error.pack()
        tk.Label(f, text=W.strip_html(tr("DIALOG_SET_HOTKEY_Hint")), bg=T.WINDOW_BG, fg=T.TEXT_MUTED,
                 font=T.font(9), justify="center", wraplength=380).pack(pady=(4, 0))
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(pady=(14, 0))
        W.RoundButton(row, tr("RNG_SETTINGS_Button_Cancel"), self.cancel, kind="ghost").pack(side="left", padx=5)
        W.RoundButton(row, tr("RNG_SETTINGS_Button_Save"), self.accept).pack(side="left", padx=5)
        self.bind("<KeyPress>", self._press)
        self.bind("<KeyRelease>", self._release)
        for seq in ("<Button-1>", "<Button-2>", "<Button-3>", "<Button-8>", "<Button-9>"):
            self.display.bind(seq, self._mouse)
        self.display.bind("<MouseWheel>", lambda e: self._set("wheel_up" if e.delta > 0 else "wheel_down"))
        self.display.bind("<Button-4>", lambda e: self._set("wheel_up"))
        self.display.bind("<Button-5>", lambda e: self._set("wheel_down"))
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - self.winfo_width()) // 2
        y = app.root.winfo_rooty() + (app.root.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _state_mods(self, e) -> set[str]:
        mods = set(self.mods)
        if e.state & 0x4:
            mods.add("ctrl")
        if e.state & 0x1:
            mods.add("shift")
        if e.state & (0x20000 if sys.platform == "win32" else 0x8):
            mods.add("alt")
        return mods

    def _press(self, e):
        low = e.keysym.lower()
        if low in _TK_MODS:
            self.mods.add(_TK_MODS[low])
            return "break"
        name = _tk_key_name(e)
        mods = self._state_mods(e)
        if name == "enter" and not mods:
            self.accept()
        elif name == "escape" and not mods:
            self.hk = None
            self.display.configure(text=format_hotkey(None))
            self.error.configure(text="")
        else:
            self._set(name, mods)
        return "break"

    def _release(self, e):
        self.mods.discard(_TK_MODS.get(e.keysym.lower(), ""))

    def _mouse(self, e):
        name = {1: "mouse_left", 2: "mouse_middle", 3: "mouse_right", 8: "mouse4", 9: "mouse5"}.get(e.num)
        mods = self._state_mods(e)
        if name in ("mouse_left", "mouse_right") and not mods:
            self.error.configure(text=tr("HOTKEY_Error_Entry_1"))
            return
        if name:
            self._set(name, mods)

    def _set(self, key: str, mods: set[str] | None = None):
        hk = HotKey(frozenset(mods or ()), key)
        if hk.is_restricted:
            self.error.configure(text=tr("HOTKEY_Error_Entry_0"))
            return
        self.hk = hk
        self.error.configure(text="")
        self.display.configure(text=format_hotkey(hk))

    def accept(self):
        self.close()
        self.on_done(self.hk)

    def cancel(self):
        self.close()

    def close(self):
        self.app.hotkeys_suspended = self._was_suspended
        self.destroy()


class App:
    def __init__(self, config: Config, backend: Backend, splash: bool = True):
        self.config = config
        self.backend = backend
        i18n.set_language(config.general.language)
        T.register_fonts()
        self.root = tk.Tk()
        self.root.withdraw()
        T.apply(self.root)
        self.root.title(f"{APP_NAME} {__version__}")
        self._set_icon()
        w, h = T.WINDOW_SIZE
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{min(w, sw - 40)}x{min(h, sh - 80)}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.root.minsize(1060, 600)

        self.events: queue.Queue = queue.Queue()
        self.manager = TableManager(config, backend, on_event=lambda k, d: self.events.put((k, d)))
        self.history = SessionHistory(config_dir() / "sessions.json")
        self.notifications: list[str] = []
        self.input = InputListener(self._on_hotkey)
        self.manager.ctrl_pressed = lambda: "ctrl" in self.input.tracker.mods
        self.gamepad: GamepadListener | None = None
        self.hotkeys_suspended = False
        self.toast = W.Toast(self.root)
        self.floating: dict[str, tk.Toplevel] = {}
        self.borders = TableBorders(self.root)
        self.table_overlays: dict[object, TableOverlay] = {}
        self.counters = {"tables": 0, "ar": 0, "stacked": 0, "hands": 0}
        self._foreground = None
        self._foreground_at = 0.0
        self._save_job = None
        self._last_hands = 0
        self.tray = None
        self.status_var = tk.StringVar(value="")
        self.pages: dict = {}
        self.current: str | None = None
        self.expanded = False

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.after(100, self._pump_events)
        self.root.after(200, self._tick)
        self._splash = self._show_splash() if splash else None

    # ================================================================== fenêtre
    def _set_icon(self):
        try:
            if sys.platform == "win32":
                self.root.iconbitmap(default=str(assets.path("images", "app.ico")))
            else:
                icon = T.image("logo.png", 64)
                if icon:
                    self.root.iconphoto(True, icon)
        except tk.TclError:
            pass

    def _show_splash(self) -> tk.Toplevel | None:
        img = T.image("splash.png", (330, 440))
        if img is None:
            self.root.deiconify()
            return None
        s = tk.Toplevel(self.root)
        s.overrideredirect(True)
        s.attributes("-topmost", True)
        tk.Label(s, image=img, bg=T.WINDOW_BG, bd=0).pack()
        s.update_idletasks()
        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        s.geometry(f"+{(sw - img.width()) // 2}+{(sh - img.height()) // 2}")
        self.root.after(1400, self._end_splash)
        return s

    def _end_splash(self):
        if self._splash:
            self._splash.destroy()
            self._splash = None
        if not self.config.general.start_minimized:
            self.root.deiconify()
        else:
            self.root.deiconify()
            self.root.iconify()

    def _build(self):
        self.shell = tk.Frame(self.root, bg=T.WINDOW_BG)
        self.shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(self.shell, bg=T.SIDE_MENU, width=T.MENU_WIDTH)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        main = tk.Frame(self.shell, bg=T.WINDOW_BG)
        main.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(main, bg=T.WINDOW_BG)
        self.content.pack(fill="both", expand=True)
        self._build_sidebar()
        self._build_status_bar(main)
        from .pages.controller import ControllerPage
        from .pages.help import ChangelogPage, HelpPage
        from .pages.home import HomePage
        from .pages.hotkeys import HotkeysPage
        from .pages.layouts import LayoutsPage
        from .pages.overlays import OverlaysPage
        from .pages.session import SessionPage
        from .pages.settings import SettingsPage
        from .pages.sites import SitesPage
        self.page_classes = {"home": HomePage, "layouts": LayoutsPage, "sites": SitesPage, "hotkeys": HotkeysPage,
                             "controller": ControllerPage, "overlays": OverlaysPage, "session": SessionPage,
                             "settings": SettingsPage, "help": HelpPage, "changelog": ChangelogPage}
        self.show_page(self.current or "home")

    def _build_sidebar(self):
        sb = self.sidebar
        head = tk.Frame(sb, bg=T.SIDE_MENU, height=64)
        head.pack(fill="x")
        head.pack_propagate(False)
        burger = tk.Label(head, text="☰", bg=T.SIDE_MENU, fg="white", font=T.font(16), width=3, cursor="hand2")
        burger.pack(side="left", padx=(8, 0))
        burger.bind("<Button-1>", lambda e: self.toggle_menu())
        self.menu_logo = tk.Label(head, image=T.image("logo.png", 34), bg=T.SIDE_MENU)
        self.menu_name = tk.Label(head, text=APP_NAME, bg=T.SIDE_MENU, fg="white", font=T.font(12, "bold"))
        self.menu_items: dict[str, tuple[tk.Frame, tk.Label, tk.Label]] = {}
        for key, glyph, title_key in MENU:
            row = tk.Frame(sb, bg=T.SIDE_MENU, height=46, cursor="hand2")
            row.pack(fill="x")
            row.pack_propagate(False)
            g = tk.Label(row, text=glyph, bg=T.SIDE_MENU, fg="white", font=T.font(15), width=3)
            g.pack(side="left", padx=(8, 0))
            t = tk.Label(row, text=tr(title_key), bg=T.SIDE_MENU, fg="white", font=T.font(10, "bold"), anchor="w")
            for w in (row, g, t):
                w.bind("<Button-1>", lambda e, k=key: self.show_page(k))
                w.bind("<Enter>", lambda e, k=key: self._hover_item(k, True))
                w.bind("<Leave>", lambda e, k=key: self._hover_item(k, False))
            W.Tooltip(g, tr(title_key))
            self.menu_items[key] = (row, g, t)
        self.hotkey_chip = tk.Label(sb, text="⏻", bg=T.SIDE_MENU, fg=T.GREEN[200], font=T.font(14), cursor="hand2")
        self.hotkey_chip.pack(side="bottom", pady=12)
        self.hotkey_chip.bind("<Button-1>", lambda e: self.manager.trigger(Action.DisableAllHotkeys))
        W.Tooltip(self.hotkey_chip, action_label(Action.DisableAllHotkeys))
        self._apply_menu_width()

    def toggle_menu(self):
        self.expanded = not self.expanded
        self._apply_menu_width()

    def _apply_menu_width(self):
        self.sidebar.configure(width=T.MENU_EXPANDED_WIDTH if self.expanded else T.MENU_WIDTH)
        for row, g, t in self.menu_items.values():
            if self.expanded:
                t.pack(side="left", fill="x", padx=(2, 8))
            else:
                t.pack_forget()
        if self.expanded:
            self.menu_logo.pack(side="left", padx=(6, 4))
            self.menu_name.pack(side="left")
        else:
            self.menu_logo.pack_forget()
            self.menu_name.pack_forget()

    def _hover_item(self, key: str, on: bool):
        if key == self.current:
            return
        color = T.PRIMARY[700] if on else T.SIDE_MENU
        for w in self.menu_items[key]:
            w.configure(bg=color)

    def _build_status_bar(self, parent):
        tk.Frame(parent, bg=T.BORDER, height=1).pack(fill="x")
        bar = tk.Frame(parent, bg=T.GRAY[50], height=34)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.status_dot = tk.Label(bar, text="●", bg=T.GRAY[50], fg=T.GREEN[400], font=T.font(9))
        self.status_dot.pack(side="left", padx=(14, 4))
        tk.Label(bar, textvariable=self.status_var, bg=T.GRAY[50], fg=T.TEXT_MUTED, font=T.font(9),
                 anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(bar, text=f"v{__version__}", bg=T.GRAY[50], fg=T.GRAY[500], font=T.font(8)).pack(side="right",
                                                                                                  padx=12)
        for icon, key, url in (("statusbar/bug.png", "APP_WINDOW_STATUS_BAR_NL_Button_Report_Issue", "/issues"),
                               ("statusbar/collaborate.png", "APP_WINDOW_STATUS_BAR_NL_Button_Collaborate", ""),
                               ("statusbar/guide.png", "APP_WINDOW_STATUS_BAR_NL_Button_Open_Guide", "#readme")):
            b = tk.Label(bar, text=" " + tr(key), image=T.image(icon, 18), compound="left", bg=T.GRAY[50],
                         fg=T.PRIMARY[700], font=T.font(9, "bold"), cursor="hand2")
            b.pack(side="right", padx=8)
            b.bind("<Button-1>", lambda e, u=url: webbrowser.open(REPO_URL + u))

    def show_page(self, key: str):
        if self.current and self.current in self.pages:
            self.pages[self.current].hide()
            self.pages[self.current].pack_forget()
        prev = self.current
        self.current = key
        if prev in self.menu_items:
            for w in self.menu_items[prev]:
                w.configure(bg=T.SIDE_MENU)
        for w in self.menu_items[key]:
            w.configure(bg=T.SIDE_MENU_SELECTED)
        page = self.pages.get(key)
        if page is None:
            page = self.pages[key] = self.page_classes[key](self)
        page.pack(fill="both", expand=True)
        page.show()

    def rebuild(self):
        """Reconstruit l'interface (changement de langue)."""
        i18n.set_language(self.config.general.language)
        self.toast.close()
        self.shell.destroy()
        self.pages.clear()
        self._build()

    # ================================================================== démarrage / arrêt
    def run(self):
        self.manager.start()
        if not self.input.start():
            self.notify(self.input.error or "pynput")
        for msg in self.backend.diagnostics():
            self.notify(msg)
        if self.config.controller.enabled:
            self.start_gamepad()
        self.apply_widgets()
        self.notify(f"{APP_NAME} {__version__} — {self.backend.name}")
        self.root.mainloop()

    def quit(self):
        self._end_session_record()
        self.save(toast=False)
        self.manager.stop()
        self.input.stop()
        if self.gamepad:
            self.gamepad.stop()
        if self.tray:
            self.tray.stop()
        self.borders.clear()
        self.root.destroy()

    def _end_session_record(self):
        record = self.manager.session.record()
        if record and self.manager.session.running:
            self.manager.session.stop()
            record = self.manager.session.record()
            self.history.add(record)
            if self.config.general.session_log:
                try:
                    self.manager.session.append_to_log(config_dir() / "sessions.csv")
                except OSError:
                    pass

    def save(self, toast: bool = True):
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self._save_job = None
        try:
            self.config.save()
        except OSError as exc:
            W.info(self.root, APP_NAME, str(exc))
            return
        self.manager.submit(self.manager.reload_settings)
        if toast:
            self.toast.show(tr("IMPORT_EXPORT_SETTINGS_NL_Status_Success"), "configuration/save_juro_location.png")

    def changed(self):
        """Un réglage a changé : application immédiate, sauvegarde différée."""
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(700, lambda: (self.save(toast=False), self.apply_widgets()))

    def notify(self, text: str):
        stamp = time.strftime("%H:%M:%S")
        self.notifications.append(f"{stamp}  {text}")
        self.notifications = self.notifications[-500:]
        self.status_var.set(text)

    # ================================================================== raccourcis
    def capture_hotkey(self, title: str, current, on_done):
        HotkeyDialog(self, title, current, on_done)

    def bind_action(self, action: Action, hk: HotKey | None) -> bool:
        reg = self.config.hotkeys
        if hk is not None:
            if hk.is_restricted:
                W.info(self.root, tr("DIALOG_SET_HOTKEY_Title"), tr("HOTKEY_Error_Entry_0"))
                return False
            other = reg.action_for(hk)
            if other is not None and other != action:
                W.info(self.root, tr("DIALOG_SET_HOTKEY_Title"),
                       f"{tr('HOTKEY_Error_Collision')}{action_label(other)}")
                return False
        reg.bind(action, hk)
        self.changed()
        return True

    def _on_hotkey(self, hk: HotKey):
        """Appelé depuis le fil pynput."""
        if self.hotkeys_suspended:
            return
        reg = self.config.hotkeys
        if reg.globally_enabled:
            for layout in self.config.layouts:
                try:
                    if layout.switch_hotkey and HotKey.parse(layout.switch_hotkey) == hk:
                        self.manager.submit(self.manager.switch_layout, layout.name)
                        return
                except ValueError:
                    continue
        action = reg.resolve(hk)
        hs = self.config.hotkey_settings
        if action is None and hs.ctrl_switches_groups and "ctrl" in hk.modifiers and reg.globally_enabled:
            base = reg.resolve(HotKey(hk.modifiers - {"ctrl"}, hk.key))
            if base is not None and base.value.startswith("Button") and int(base.value[6:]) <= 8:
                action = Action(f"Button{int(base.value[6:]) + 8}")
        if action is None:
            return
        if action in (Action.IncreaseBet, Action.DecreaseBet) and hk.key in ("wheel_up", "wheel_down") \
                and not hs.wheel_betting:
            return
        if hk.is_mouse:  # souris : seulement au-dessus d'une table
            m = self.manager
            m.submit(lambda: m.hovered_table() is not None and m.perform(action))
        else:
            self.manager.trigger(action)

    def start_gamepad(self) -> bool:
        if self.gamepad:
            return True
        self.gamepad = GamepadListener(lambda b: self.root.after(0, lambda: self._on_gamepad(b)))
        if not self.gamepad.start():
            self.gamepad = None
            return False
        self.toast.show(tr("CONTROLLER_PAGE_TOASTER_CONTROLLER_CONNECTED_NL"), "controller/controller_connected.png")
        return True

    def stop_gamepad(self):
        if self.gamepad:
            self.gamepad.stop()
            self.gamepad = None
            self.toast.show(tr("CONTROLLER_PAGE_TOASTER_CONTROLLER_DISCONNECTED_NL"), "controller/controller_mini.png")

    def _on_gamepad(self, button: str):
        if self.hotkeys_suspended:
            return
        action = self.config.hotkeys.action_for_gamepad(button)
        if action is not None and (self.config.hotkeys.globally_enabled or action == Action.DisableAllHotkeys):
            self.manager.trigger(action)

    # ================================================================== événements du gestionnaire
    def _pump_events(self):
        refresh = False
        try:
            while True:
                kind, data = self.events.get_nowait()
                refresh |= self._handle_event(kind, data)
        except queue.Empty:
            pass
        if refresh and self.current in self.pages:
            self.pages[self.current].refresh_live()
        self.root.after(120, self._pump_events)

    def _handle_event(self, kind: str, data: dict) -> bool:
        g = self.config.general
        if kind == "tables":
            return True
        if kind == "action_required":
            if g.ar_sound_enabled:
                sounds.play(g.ar_sound, g.ar_volume)
            if self.gamepad and self.config.controller.vibrate_on_turn:
                self.gamepad.vibrate()
            rng = self.floating.get("rng")
            if isinstance(rng, RngOverlay) and self.config.rng.roll_on == "my_turn":
                rng.roll()
        elif kind == "delayed_alarm":
            sounds.play(g.delayed_alarm_sound, g.delayed_alarm_volume)
        elif kind == "table_opened":
            self.notify(f"{data['site']} : {data['title']}")
            return True
        elif kind == "table_closed":
            return True
        elif kind == "layout_changed":
            self.notify(f"{tr('LAYOUT_CONFIGURATION_NL_Label_Active_Layout')} {data['name']}")
            self.toast.show(f"{tr('LAYOUT_CONFIGURATION_NL_Label_Active_Layout')} {data['name']}", "toastr/tiling.png")
            return True
        elif kind == "ask_layout_switch":
            msg = f"{tr('LAYOUT_CONFIGURATION_NL_ON_LAYOUT_SWITCH_Message')}{data['name']} ?"
            ok = W.ask_yes_no(self.root, tr("LAYOUT_CONFIGURATION_NL_ON_LAYOUT_SWITCH_Title"), msg,
                              tr("AUTO_FOCUS_MOUSE_FREE_DIALOG_YES"), tr("AUTO_FOCUS_MOUSE_FREE_DIALOG_IGNORE"),
                              image="layout/ask_before.png")
            self.manager.submit(self.manager.confirm_pending_switch, ok)
        elif kind == "hotkeys_toggled":
            text = tr("HOTKEYS_USAGE_ON_VIEW_UNLOADED") if data["enabled"] else tr("SETTINGS_NL_Label_Disable_All_Hotkeys")
            self.toast.show(text, "toastr/hotkeys.png")
            self.hotkey_chip.configure(fg=T.GREEN[200] if data["enabled"] else T.RED[300])
        elif kind == "table_locked":
            self.toast.show(f"{action_label(Action.LockTableFromDynamicFlow)} : {'✔' if data['locked'] else '✘'}",
                            "layout/hotkeys/lock_table.png")
            return True
        elif kind == "break_reminder":
            self.toast.show("☕  Pause ?", "session/notify_me.png", 8000)
            sounds.play("Bubble", g.ar_volume)
        elif kind == "session_tables_goal":
            self.toast.show(f"{tr('SESSION_TIME_PAGE_NL_Label_Notify_Me_After_I_Have_Opened')} {data['tables']} "
                            f"{tr('SESSION_TIME_PAGE_NL_Label_Tables')}", "session/notify_after_opened.png", 8000)
            sounds.play("Shimmer", g.ar_volume)
        elif kind == "session_hands_goal":
            self.toast.show(tr("SESSION_TIME_PAGE_NL_TOAST_You_Have_Played_N_Hands").replace("#hands#",
                                                                                            str(data["hands"])),
                            "session/notify_after_played.png", 8000)
            sounds.play("Shimmer", g.ar_volume)
        elif kind == "session_ended":
            record = data.get("record")
            if record and record.get("duration_s", 0) >= 60:
                self.history.add(record)
                self.toast.show(tr("SESSION_TIME_PAGE_NL_TOAST_Session_Saved"), "session/stop_session.png")
            return True
        elif kind == "error":
            self.notify(f"⚠ {data['message']}")
        elif kind == "ui_action":
            self._ui_action(data["action"])
        return False

    def _ui_action(self, action: Action):
        if action == Action.RNGMoveToPointer:
            if not isinstance(self.floating.get("rng"), RngOverlay):
                self.config.general.show_rng = True
                self.apply_widgets()
            x, y = self.backend.cursor_pos()
            self.floating["rng"].move_to(x, y)
        elif action == Action.PeekActiveLayoutHotKey:
            LayoutPeek(self.root, self.manager.engine.layout, slot_labels())
        elif action in (Action.OpenMenu, Action.ResetMainWindowPosition):
            if self.tray:
                self._from_tray()
            self.root.deiconify()
            if action == Action.ResetMainWindowPosition:
                self.root.geometry("+80+80")
            self.root.lift()
            self.root.focus_force()
        elif action == Action.OpenNotificationsDebugWindow:
            self.root.deiconify()
            self.show_page("help")
            self.pages["help"].show_diagnostics()
        elif action == Action.ToggleBBMode:
            self.config.general.bb_mode = not self.config.general.bb_mode
            self.toast.show(f"{tr('HOTKEYS_NL_Label_Toggle_BB_Mode')} : {'✔' if self.config.general.bb_mode else '✘'}",
                            "toastr/bb_conversion.png")
        elif action == Action.ShowControllerCursor:
            x, y = self.backend.cursor_pos()
            cur = tk.Toplevel(self.root)
            cur.overrideredirect(True)
            cur.attributes("-topmost", True)
            tk.Label(cur, image=T.image("controller/cursor.png", 40), bd=0, bg=T.WINDOW_BG).pack()
            cur.geometry(f"+{x - 8}+{y - 4}")
            self.root.after(900, cur.destroy)
        elif action == Action.HideShowBoard:
            self.toast.show(tr("SITE_CONFIGURATION_DETAILS_NL_Label_Hide_Board_If_All_In") + " — data provider",
                            "site/hide_board.png")

    # ================================================================== widgets flottants
    def _moved(self, name: str):
        def cb(x, y):
            self.config.session.widget_positions[name] = [x, y]
            self.changed()
        return cb

    def apply_widgets(self):
        s, o, g = self.config.session, self.config.overlays, self.config.general
        pos = s.widget_positions
        c = self.counters
        m = self.manager
        specs = {
            "timer": (s.timer_enabled and s.show_timer_widget, lambda: SessionTimerWidget(
                self.root, m.session.format_elapsed, lambda: m.session.running,
                lambda: m.submit(m.session.start), lambda: m.submit(m.end_session), self._moved("timer"),
                pos.get("timer"))),
            "open_tables": (s.show_open_tables_widget, lambda: CounterWidget(
                self.root, "session/slot_tables_widget.png", lambda: c["tables"], self._moved("open_tables"),
                pos.get("open_tables") or (20, 110))),
            "ar_tables": (s.show_ar_tables_widget, lambda: CounterWidget(
                self.root, "session/ar_tables_widget.png", lambda: c["ar"], self._moved("ar_tables"),
                pos.get("ar_tables") or (20, 160))),
            "hands": (s.show_hands_widget, lambda: CounterWidget(
                self.root, "session/hands_counter_widget.png", lambda: c["hands"], self._moved("hands"),
                pos.get("hands") or (20, 210))),
            "ar_counter": (o.ar_counter, lambda: CounterWidget(
                self.root, "overlay/ar_table.png", lambda: c["ar"], self._moved("ar_counter"),
                pos.get("ar_counter") or (20, 260))),
            "st_counter": (o.st_counter, lambda: CounterWidget(
                self.root, "overlay/st_table.png", lambda: c["stacked"], self._moved("st_counter"),
                pos.get("st_counter") or (20, 310))),
            "rng": (g.show_rng, lambda: RngOverlay(self.root, self.config.rng, lambda x, y: self.changed())),
        }
        for name, (wanted, factory) in specs.items():
            win = self.floating.get(name)
            if wanted and win is None:
                self.floating[name] = factory()
            elif not wanted and win is not None:
                win.destroy()
                del self.floating[name]
        if not o.bet_buttons and not o.screenshot and not self._data_overlays():
            for ov in self.table_overlays.values():
                ov.destroy()
            self.table_overlays.clear()

    def reset_widget(self, name: str):
        win = self.floating.pop(name, None)
        if win is not None:
            win.destroy()
        self.apply_widgets()

    def _data_overlays(self) -> bool:
        o = self.config.overlays
        return self.manager.data_provider is not None and any(
            (o.pot_odds, o.pot_odds_ratio, o.spr, o.effs, o.mdf, o.bluff_equity))

    # ================================================================== bordures et overlays de table
    def _tick(self):
        try:
            self._tick_inner()
        except tk.TclError:
            pass
        except Exception:
            log.exception("rafraîchissement des overlays")
        self.root.after(200, self._tick)

    def _tick_inner(self):
        m, b, o = self.manager, self.config.border, self.config.overlays
        now = time.time()
        with m.lock:
            self.counters.update(m.counters())
            tables = [(t.handle, t.needs_action, t.action_since, t.minimized) for t in m.engine.poker_tables()]
            rects = {h: m._table_rect(h) for h, *_ in tables}
            urgent = m.engine.most_urgent()
        rng = self.floating.get("rng")
        if isinstance(rng, RngOverlay) and self.config.rng.roll_on == "hand" and self.counters["hands"] != self._last_hands:
            rng.roll()
        self._last_hands = self.counters["hands"]
        # Bordures « c'est votre tour »
        items = {}
        if b.enabled:
            waiting = [t for t in tables if t[1] and not t[3] and rects.get(t[0])]
            if b.only_most_urgent:
                waiting = [t for t in waiting if urgent and t[0] == urgent.handle]
            for h, _, since, _ in waiting:
                items[h] = (rects[h], border_color(now - (since or now), b))
        if b.highlight_focused:
            if now - self._foreground_at > 0.6:
                self._foreground_at = now
                try:
                    self._foreground = self.backend.foreground()
                except Exception:
                    self._foreground = None
            if self._foreground in rects and rects[self._foreground] and self._foreground not in items:
                items[self._foreground] = (rects[self._foreground], b.focused_color)
        self.borders.update(items, b.size, blink_off=b.blink and int(now * 2) % 2 == 1)
        # Overlays attachés aux tables
        if not (o.bet_buttons or o.screenshot or self._data_overlays()):
            return
        hs = self.config.hotkey_settings
        alive = set()
        for h, needs, _, minimized in tables:
            rect = rects.get(h)
            if rect is None or minimized:
                continue
            alive.add(h)
            ov = self.table_overlays.get(h)
            if ov is None:
                ov = self.table_overlays[h] = TableOverlay(self.root, h, self._overlay_bet, self._overlay_screenshot)
            labels = []
            if o.bet_buttons and (needs or o.bet_buttons_always_visible):
                for btn in hs.bet_buttons[:o.bet_buttons_count]:
                    labels.append(f"{btn.preflop_bb:g}bb" if btn.preflop_bb else
                                  (f"{btn.postflop_pct:g}%" if btn.postflop_pct else btn.label))
                if o.bet_buttons_last_allin and labels:
                    labels[-1] = "All-in"
            ov.update(rect, labels, o.screenshot, self._data_text(h), True)
        for h in [h for h in self.table_overlays if h not in alive]:
            self.table_overlays.pop(h).destroy()

    def _data_text(self, handle) -> str:
        if not self._data_overlays():
            return ""
        snap = self.manager._snapshot(handle)
        if snap is None or not snap.pot:
            return ""
        o, parts = self.config.overlays, []
        if o.pot_odds and snap.to_call:
            parts.append(f"PO {pokermath.pot_odds(snap.pot, snap.to_call) * 100:.0f}%")
        if o.pot_odds_ratio and snap.to_call:
            parts.append(f"{pokermath.pot_odds_ratio(snap.pot, snap.to_call):.1f}:1")
        if o.spr and snap.hero_stack:
            parts.append(f"SPR {pokermath.spr(snap.hero_stack, snap.pot):.1f}")
        if o.effs and snap.hero_stack:
            parts.append(f"EFF {snap.hero_stack:g}")
        if o.mdf and snap.to_call:
            parts.append(f"MDF {pokermath.mdf(snap.pot - snap.to_call, snap.to_call) * 100:.0f}%")
        if o.bluff_equity and snap.to_call:
            parts.append(f"BE {pokermath.bluff_break_even(snap.pot - snap.to_call, snap.to_call) * 100:.0f}%")
        return "  ".join(parts)

    def _overlay_bet(self, handle, index: int):
        o = self.config.overlays
        if o.bet_buttons_last_allin and index == o.bet_buttons_count:
            self.manager.trigger(Action.AllIn, handle)
        else:
            self.manager.submit(self.manager.overlay_bet, handle, index)

    def _overlay_screenshot(self, handle):
        with self.manager.lock:
            rect = self.manager._table_rect(handle)
        if rect is None:
            return
        folder = Path(self.config.overlays.screenshot_folder or Path.home() / "Pictures" / APP_NAME)
        ov = self.table_overlays.get(handle)
        if ov:
            ov.win.withdraw()
        self.root.update_idletasks()
        try:
            path = screenshot(rect, folder)
        finally:
            if ov:
                ov.win.deiconify()
        if path:
            self.toast.show(str(path), "overlay/customization.png")

    # ================================================================== barre système
    def _on_unmap(self, e):
        if e.widget is self.root and self.config.general.minimize_to_tray and self.tray is None:
            self.root.after(50, self._to_tray)

    def _to_tray(self):
        if self.root.state() != "iconic":
            return
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return
        self.root.withdraw()
        menu = pystray.Menu(pystray.MenuItem(APP_NAME, lambda: self.root.after(0, self._from_tray), default=True),
                            pystray.MenuItem("✕", lambda: self.root.after(0, self.quit)))
        self.tray = pystray.Icon("fukuroku", Image.open(assets.path("images", "logo.png")), APP_NAME, menu)
        self.tray.run_detached()

    def _from_tray(self):
        if self.tray:
            self.tray.stop()
            self.tray = None
        self.root.deiconify()
        self.root.lift()
