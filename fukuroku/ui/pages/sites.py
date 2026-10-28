"""Configuration des Sites : tuiles des salles, puis détails par salle
(positionnement, contournement des hotkeys, confort, rebuy, popups, détection)."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from ...hotkeys import HotKey
from ...sites import DEFAULT_CLICK_POINTS, SiteDefinition
from .. import theme as T
from .. import widgets as W
from . import NOT_PORTED, HotkeyField, Page, bold, combo, own, radio_group, spin, tr

D = "SITE_CONFIGURATION_DETAILS_NL_"


class SitesPage(Page):
    title_key = "APP_HAMBURGER_MENU_ITEM_Title_Sites"

    def build(self):
        self.list_view = tk.Frame(self, bg=T.WINDOW_BG)
        self.detail: tk.Frame | None = None
        bar = tk.Frame(self.list_view, bg=T.WINDOW_BG)
        bar.pack(fill="x", padx=28, pady=(20, 8))
        W.page_title(bar, tr(self.title_key)).pack(side="left")
        W.RoundButton(bar, "+  " + own("Ajouter une salle", "Add a room"), self._add_site,
                      kind="secondary").pack(side="right")
        self.scroll = W.ScrollFrame(self.list_view)
        self.scroll.pack(fill="both", expand=True, padx=(28, 8))
        self.list_view.pack(fill="both", expand=True)

    def refresh(self):
        if self.detail is not None:
            return
        grid = self.scroll.inner
        for w in grid.winfo_children():
            w.destroy()
        counts: dict[str, int] = {}
        with self.app.manager.lock:
            for t in self.app.manager.engine.poker_tables():
                counts[t.site_id] = counts.get(t.site_id, 0) + 1
        for i, site in enumerate(self.cfg.sites):
            card = tk.Frame(grid, bg=T.WINDOW_BG, highlightthickness=1, highlightbackground=T.BORDER, padx=12, pady=10,
                            cursor="hand2", width=228, height=104)
            card.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="nsew")
            card.grid_propagate(False)
            top = tk.Frame(card, bg=T.WINDOW_BG)
            top.pack(fill="x")
            name = tk.Label(top, text="♠ " + site.name, bg=T.WINDOW_BG, fg=T.PRIMARY[900], font=T.font(10, "bold"),
                            anchor="w", wraplength=150, justify="left")
            name.pack(side="left")
            v = self.keep(tk.BooleanVar(value=site.enabled))
            v.trace_add("write", lambda *_, s=site, v=v: (setattr(s, "enabled", v.get()), self.app.changed()))
            W.ToggleSwitch(top, v).pack(side="right")
            sub = tk.Label(card, text=", ".join(site.processes[:3]) or "—", bg=T.WINDOW_BG, fg=T.TEXT_MUTED,
                           font=T.font(8), anchor="w")
            sub.pack(fill="x", pady=(4, 0))
            n = counts.get(site.id, 0)
            stat = tk.Label(card, text=f"● {n} table(s)" if n else "", bg=T.WINDOW_BG, fg=T.GREEN[500],
                            font=T.font(8, "bold"), anchor="w")
            stat.pack(fill="x", side="bottom")
            for w in (card, name, sub, stat):
                w.bind("<Button-1>", lambda e, s=site: self.open_site(s))
            card.bind("<Enter>", lambda e, c=card: c.configure(highlightbackground=T.ACCENT))
            card.bind("<Leave>", lambda e, c=card: c.configure(highlightbackground=T.BORDER))
            self.scroll.bind_all_wheel(card)

    def _add_site(self):
        n = 1
        while self.cfg.site(f"custom{n}"):
            n += 1
        site = SiteDefinition(f"custom{n}", own(f"Salle personnalisée {n}", f"Custom room {n}"))
        self.cfg.sites.append(site)
        self.app.changed()
        self.open_site(site)

    def open_site(self, site: SiteDefinition):
        self.list_view.pack_forget()
        self.detail = SiteDetail(self, site)
        self.detail.pack(fill="both", expand=True)

    def close_site(self):
        if self.detail:
            self.detail.destroy()
            self.detail = None
        self.list_view.pack(fill="both", expand=True)
        self.refresh()


class SiteDetail(tk.Frame):
    def __init__(self, page: SitesPage, site: SiteDefinition):
        super().__init__(page, bg=T.WINDOW_BG)
        self.page, self.app, self.site = page, page.app, site
        bar = tk.Frame(self, bg=T.WINDOW_BG)
        bar.pack(fill="x", padx=28, pady=(20, 8))
        back = tk.Label(bar, text="‹ " + tr("APP_HAMBURGER_MENU_ITEM_Title_Back"), bg=T.WINDOW_BG, fg=T.ACCENT,
                        font=T.font(10, "bold"), cursor="hand2")
        back.pack(side="left", padx=(0, 14))
        back.bind("<Button-1>", lambda e: self._close())
        W.page_title(bar, f"{tr(D + 'Title_Site_Configuration')} — {site.name}").pack(side="left")
        W.RoundButton(bar, tr(D + "Button_Save_Changes"), self._save).pack(side="right")
        self.vars: list[tk.Variable] = []
        tabs = [(tr(D + "Tab_Header_Table_Positioning"), self._tab_positioning),
                (tr(D + "Tab_Header_Hoytkeys_Baypassing"), self._tab_site_keys),
                (own("Détection & clics", "Detection & clicks"), self._tab_detection),
                (tr(D + "Tab_Header_Confort_Features"), self._tab_comfort),
                (tr(D + "Tab_Header_Rebuy_Topup"), self._tab_rebuy),
                (tr(D + "Tab_Header_Popup_Handling"), self._tab_popups)]
        bar = page.tabs(self, [t for t, _ in tabs], [b for _, b in tabs])
        bar.select(0)

    def _v(self, v):
        self.vars.append(v)
        return v

    def _attr(self, attr: str, kind=bool):
        cls = {bool: tk.BooleanVar, str: tk.StringVar, int: tk.IntVar, float: tk.DoubleVar}[kind]
        v = self._v(cls(value=getattr(self.site, attr)))

        def write(*_):
            try:
                setattr(self.site, attr, kind(v.get()))
            except (tk.TclError, ValueError):
                return
            self.app.changed()
        v.trace_add("write", write)
        return v

    def _close(self):
        self._compile()
        self.page.close_site()

    def _compile(self) -> bool:
        try:
            self.site.__post_init__()
            return True
        except re.error as exc:
            W.info(self, self.site.name, f"Regex : {exc}")
            return False

    def _save(self):
        if self._compile():
            self.app.save()

    # ------------------------------------------------------------------ Positionnement des tables
    def _tab_positioning(self, f):
        s = self.site
        tiling = self._attr("tiling")
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(fill="x", pady=(4, 10))
        W.ToggleSwitch(row, tiling).pack(side="left")
        lbl = bold(row, "", size=11)
        lbl.pack(side="left", padx=10)
        upd = lambda *_: lbl.configure(text=tr(D + ("Toggle_Tiling_Enabled" if tiling.get() else "Toggle_Tiling_Disabled")))
        tiling.trace_add("write", upd)
        upd()
        card = W.Card(f)
        card.pack(fill="x", padx=(0, 12), pady=4)
        head = tk.Frame(card, bg=T.WINDOW_BG)
        head.pack(fill="x")
        tk.Label(head, image=T.image("site/new_table.png", 40), bg=T.WINDOW_BG).pack(side="left")
        txt = tk.Frame(head, bg=T.WINDOW_BG)
        txt.pack(side="left", padx=10)
        bold(txt, tr(D + "Label_New_Table_Detected"), size=11).pack(anchor="w")
        W.label(txt, tr(D + "Label_When_A_Table_Is_Detected"), muted=True, size=9).pack(anchor="w")
        radio_group(card, self._attr("new_table", str), [
            ("playing", tr(D + "Option_Send_Tables_To_Playing_Area")),
            ("observer", tr(D + "Option_Send_Tables_To_Observer_Area")),
            ("nothing", tr(D + "Option_Do_Nothing"))]).pack(anchor="w", padx=50, pady=4)

        card = W.Card(f)
        card.pack(fill="x", padx=(0, 12), pady=4)
        head = tk.Frame(card, bg=T.WINDOW_BG)
        head.pack(fill="x")
        tk.Label(head, image=T.image("site/ar.png", 40), bg=T.WINDOW_BG).pack(side="left")
        txt = tk.Frame(head, bg=T.WINDOW_BG)
        txt.pack(side="left", padx=10)
        bold(txt, tr(D + "Label_Action_Required"), size=11).pack(anchor="w")
        W.label(txt, tr(D + "Label_When_My_Turn_Ended_At_A_Table_In_Action_Required_Slot"), muted=True,
                size=9, wrap=600).pack(anchor="w")
        rv = self.page.var(self.app.config.placement, "return_to_previous_slot")
        W.SettingRow(card, None, tr(D + "Option_Send_The_Table_To_The_Area_Where_It_Was_Before"), rv).pack(fill="x",
                                                                                                         padx=40)

        card = W.Card(f)
        card.pack(fill="x", padx=(0, 12), pady=4)
        head = tk.Frame(card, bg=T.WINDOW_BG)
        head.pack(fill="x")
        tk.Label(head, image=T.image("site/in_hand.png", 40), bg=T.WINDOW_BG).pack(side="left")
        txt = tk.Frame(head, bg=T.WINDOW_BG)
        txt.pack(side="left", padx=10)
        bold(txt, tr(D + "Label_In_Hand_Slots"), size=11).pack(anchor="w")
        W.label(txt, tr(D + "Label_When_Should_Table_Be_Moved_To_In_Hand_Slots"), muted=True, size=9).pack(anchor="w")
        radio_group(card, self._attr("in_hand_trigger", str), [
            ("new_hand", tr(D + "Option_Move_Table_To_Slot_Whenever_I_Start_A_New_Hand")),
            ("vpip", tr(D + "Option_Move_Table_To_Slot_Only_If_I_Voluntarily_Put_Money_In_The_Hand")),
            ("first_action", own("Déplacer la table vers le slot dès ma première action requise dans la main",
                                 "Move the table to the slot on my first required action in the hand"))
        ]).pack(anchor="w", padx=50, pady=4)
        W.banner(card, own("Sans fournisseur de données, « In Hand » commence à la première action requise et "
                           "se termine après 25 s sans action.",
                           "Without a data provider, “In Hand” starts on the first required action and ends "
                           "after 25 s without action.")).pack(fill="x", pady=(4, 0))

    # ------------------------------------------------------------------ Contournement des hotkeys
    def _tab_site_keys(self, f):
        W.label(f, tr(D + "Label_Tell_Jurojin_Your_Hotkey_Bindings"), muted=True, wrap=760).pack(anchor="w", pady=(4, 8))
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack(anchor="w")
        keys = (("fold", "Label_Fold"), ("check", "Label_Check_Call"), ("bet", "Label_Bet_Raise"),
                ("allin", "Label_All_In"), ("increment", "Label_Increment"), ("decrement", "Label_Decrement"),
                ("toggle_bb", "Label_Toggle_BB_Mode"), ("button1", "Label_Button1"), ("button2", "Label_Button2"),
                ("button3", "Label_Button3"), ("button4", "Label_Button4"))
        for i, (k, label) in enumerate(keys):
            cell = tk.Frame(grid, bg=T.GRAY[50], padx=12, pady=8, highlightthickness=1, highlightbackground=T.BORDER)
            cell.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="nsew")
            text = tr(D + label) if k != "increment" else tr("HOTKEYS_NL_Label_Increment")
            bold(cell, text, bg=T.GRAY[50], fg=T.PRIMARY[800]).pack(anchor="w")
            HotkeyField(cell, self.app, lambda k=k: self.site.site_keys.get(k) or None,
                        lambda hk, k=k: self._set_site_key(k, hk), bg=T.GRAY[50], title=text).pack(anchor="w", pady=(4, 0))
        tk.Label(f, image=T.image("site/keyboard.png", 70), bg=T.WINDOW_BG).pack(anchor="w", pady=8)

    def _set_site_key(self, k: str, hk: HotKey | None) -> bool:
        if hk is None:
            self.site.site_keys.pop(k, None)
        else:
            self.site.site_keys[k] = str(hk)
        self.app.changed()
        return True

    # ------------------------------------------------------------------ Détection & clics (Fukuroku)
    def _tab_detection(self, f):
        W.banner(f, own("L'original reconnaît chaque salle par une DLL chiffrée ; ici tout est déclaratif et modifiable.",
                        "The original recognises each room through an encrypted DLL; here everything is "
                        "declarative and editable.")).pack(fill="x", pady=(4, 8), padx=(0, 12))
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack(anchor="w", fill="x")
        s = self.site
        fields = (("name", own("Nom", "Name"), str), ("table_title", own("Regex titre de table", "Table title regex"), str),
                  ("lobby_title", own("Regex titre du lobby", "Lobby title regex"), str),
                  ("replay_title", own("Regex titre du replayer", "Replayer title regex"), str),
                  ("exclude_title", own("Regex titres exclus", "Excluded titles regex"), str),
                  ("select_all_keys", own("Touches « tout sélectionner » du champ de mise", "Bet box select-all keys"), str))
        for i, (attr, text, kind) in enumerate(fields):
            W.label(grid, text, bold=True).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 12))
            ttk.Entry(grid, textvariable=self._attr(attr, kind), width=60).grid(row=i, column=1, sticky="w")
        r = len(fields)
        for attr, text in (("processes", own("Processus", "Processes")), ("window_classes", own("Classes de fenêtre", "Window classes"))):
            v = self._v(tk.StringVar(value=", ".join(getattr(s, attr))))
            v.trace_add("write", lambda *_, a=attr, v=v: (setattr(s, a, [p.strip() for p in v.get().split(",") if p.strip()]),
                                                          self.app.changed()))
            W.label(grid, text, bold=True).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(grid, textvariable=v, width=60).grid(row=r, column=1, sticky="w")
            r += 1
        nums = tk.Frame(f, bg=T.WINDOW_BG)
        nums.pack(anchor="w", pady=6)
        W.label(nums, own("Ratio des tables", "Table aspect ratio"), bold=True).pack(side="left")
        spin(nums, self._attr("table_aspect", float), 0.5, 3.0, 0.01, 6).pack(side="left", padx=(6, 20))
        W.label(nums, own("Largeur min.", "Min. width"), bold=True).pack(side="left")
        spin(nums, self._attr("min_table_width", int), 100, 3000, 10, 6).pack(side="left", padx=6)
        W.RoundButton(nums, own("Tester la détection", "Test detection"), self._test, kind="secondary", height=30,
                      font_size=9).pack(side="left", padx=20)

        self.page.separator(f)
        W.section(f, own("Calibration des clics", "Click calibration")).pack(anchor="w")
        W.label(f, own("Choisissez un point, cliquez sur Calibrer puis placez le curseur dessus dans une table "
                       "(capture après 3 s).", "Pick a point, click Calibrate, then hover it in a table "
                       "(captured after 3 s)."), muted=True, size=9, wrap=760).pack(anchor="w")
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=6)
        self.point = self._v(tk.StringVar(value="fold"))
        combo(row, self.point, list(DEFAULT_CLICK_POINTS), 20).pack(side="left")
        self.point_info = W.label(row, "", muted=True, size=9)
        self.point_info.pack(side="left", padx=10)
        self.point.trace_add("write", lambda *_: self._show_point())
        self._show_point()
        W.RoundButton(row, own("Calibrer", "Calibrate"), self._calibrate_point, kind="secondary", height=30,
                      font_size=9).pack(side="left", padx=6)

        self.page.separator(f)
        W.section(f, own("Détection « action requise » (sonde de pixel)", "“Action required” detection (pixel probe)")
                  ).pack(anchor="w")
        en = self._v(tk.BooleanVar(value=s.probe.enabled))
        en.trace_add("write", lambda *_: (setattr(s.probe, "enabled", en.get()), self.app.changed()))
        W.SettingRow(f, "site/ar.png", own("Activer la sonde", "Enable probe"), en,
                     subtitle=own("Survolez un bouton d'action visible (Fold) quand c'est votre tour, puis Calibrer.",
                                  "Hover a visible action button (Fold) when it is your turn, then Calibrate.")
                     ).pack(fill="x", padx=(0, 12))
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=4)
        W.label(row, own("Tolérance", "Tolerance"), bold=True).pack(side="left")
        tol = self._v(tk.IntVar(value=s.probe.tolerance))
        tol.trace_add("write", lambda *_: self._set_tolerance(tol))
        spin(row, tol, 5, 255, 5, 5).pack(side="left", padx=6)
        self.probe_swatch = tk.Label(row, text="      ", bg="#%02x%02x%02x" % tuple(s.probe.color))
        self.probe_swatch.pack(side="left", padx=10)
        W.RoundButton(row, own("Calibrer la sonde", "Calibrate probe"), self._calibrate_probe, kind="secondary",
                      height=30, font_size=9).pack(side="left", padx=6)
        if s.id.startswith("custom"):
            W.RoundButton(f, own("Supprimer cette salle", "Delete this room"), self._delete, kind="danger",
                          height=30, font_size=9).pack(anchor="w", pady=12)

    def _set_tolerance(self, v):
        try:
            self.site.probe.tolerance = int(v.get())
            self.app.changed()
        except (tk.TclError, ValueError):
            pass

    def _show_point(self):
        p = self.site.click_point(self.point.get())
        self.point_info.configure(text=f"({p[0]:.3f}, {p[1]:.3f})" if p else "—")

    def _under_cursor(self):
        m = self.app.manager
        x, y = self.app.backend.cursor_pos()
        with m.lock:
            w = self.app.backend.window_at(x, y, m.table_windows())
        return x, y, w

    def _calibrate_point(self):
        name = self.point.get()
        self.app.notify(own(f"Placez le curseur sur « {name} » dans une table…", f"Hover “{name}” in a table…"))

        def capture():
            x, y, w = self._under_cursor()
            if not w:
                self.app.notify(own("Aucune table sous le curseur", "No table under the cursor"))
                return
            self.site.click_points[name] = tuple(round(v, 4) for v in w.rect.to_fraction(x, y))
            self.app.changed()
            self._show_point()
            self.app.notify(f"{name} → {self.site.click_points[name]}")
        self.after(3000, capture)

    def _calibrate_probe(self):
        self.app.notify(own("Survolez un bouton d'action visible…", "Hover a visible action button…"))

        def capture():
            x, y, w = self._under_cursor()
            if not w:
                self.app.notify(own("Aucune table sous le curseur", "No table under the cursor"))
                return
            color = self.app.backend.pixel(x, y)
            if color is None:
                self.app.notify(own("Lecture de pixel indisponible", "Pixel reading unavailable"))
                return
            p = self.site.probe
            p.fx, p.fy = (round(v, 4) for v in w.rect.to_fraction(x, y))
            p.color, p.enabled = tuple(color), True
            self.probe_swatch.configure(bg="#%02x%02x%02x" % tuple(color))
            self.app.changed()
            self.app.notify(f"Probe : {color}")
        self.after(3000, capture)

    def _test(self):
        if not self._compile():
            return
        found = []
        for w in self.app.backend.list_windows():
            if self.site.processes and not self.site.matches_process(w.process_name):
                continue
            role = ("table" if self.site.is_table(w.title, w.class_name, w.rect.w, w.rect.h) else
                    "lobby" if self.site.is_lobby(w.title) else "replay" if self.site.is_replay(w.title) else None)
            if role:
                found.append(f"[{role}] {w.title}")
        W.info(self, self.site.name, "\n".join(found[:30]) or tr("SITE_VALIDATION_OPEN_BEFORE_SCANNING"))

    def _delete(self):
        if W.ask_yes_no(self, self.site.name, own("Supprimer cette salle ?", "Delete this room?"),
                        tr("DIALOG_DELETE_LAYOUT_NL_Button_Delete"), tr("DIALOG_DELETE_LAYOUT_NL_Button_Cancel"),
                        danger=True):
            self.app.config.sites.remove(self.site)
            self.app.changed()
            self.page.close_site()

    # ------------------------------------------------------------------ fonctions d'origine non portées
    def _unported(self, f, rows, reason=NOT_PORTED):
        W.banner(f, own(*reason), kind="lock").pack(fill="x", pady=(4, 8), padx=(0, 12))
        for icon, key in rows:
            W.SettingRow(f, icon, tr(key), tk.BooleanVar(value=False), enabled=False).pack(fill="x", padx=(0, 12))

    def _tab_comfort(self, f):
        self._unported(f, (("site/bb_mode.png", D + "Label_BB_Conversion"),
                           ("site/font_size.png", D + "Label_Font_Size"),
                           ("site/auto_timebank.png", D + "Label_Auto_Timebank"),
                           ("site/sitting.png", D + "Label_Avoid_Sitting_Out"),
                           ("site/spins.png", D + "Label_Keep_The_Spins_Rolling"),
                           ("site/hide_hero_balance.png", D + "Label_Hide_Hero_Balance"),
                           ("site/copy_player_name.png", D + "Label_Copy_Player_Name"),
                           ("site/hide_board.png", D + "Label_Hide_Board_If_All_In"),
                           ("site/color_stack.png", D + "Label_Color_Stacks")))

    def _tab_rebuy(self, f):
        self._unported(f, (("site/topup.png", D + "Label_Auto_Top-Up_For_Cash_Games"),
                           ("site/topup.png", D + "Label_When_I_Run_Out_Of_Chips_On_Table_Rebuy_With")))

    def _tab_popups(self, f):
        self._unported(f, (("site/close_all_popups.png", D + "Label_Close_Or_Accept_All_Popups_With_A_Single_Option"),
                           ("site/popup_rules.png", D + "Label_My_Popups")))
