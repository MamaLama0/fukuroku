"""Accueil : sites de poker actifs, compteurs, tables gérées et actions rapides."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import APP_NAME
from ...hotkeys import Action
from ...layout import SLOT_COLORS
from .. import theme as T
from .. import widgets as W
from . import Page, action_label, bold, combo, slot_labels, tr


class HomePage(Page):
    title_key = "APP_HAMBURGER_MENU_ITEM_Title_Home"

    def build(self):
        self.header(tr(self.title_key))
        body = tk.Frame(self, bg=T.WINDOW_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 16))

        # Compteurs (style widgets de session)
        stats = tk.Frame(body, bg=T.WINDOW_BG)
        stats.pack(fill="x")
        self.stat_labels = {}
        for key, icon, title in (("tables", "session/slot_tables_widget.png",
                                  tr("SESSION_TIME_PAGE_NL_Open_Tables")),
                                 ("ar", "session/ar_tables_widget.png", tr("SESSION_TIME_PAGE_NL_Label_Show_Ar_Tables_Widget")),
                                 ("stacked", "overlay/st_table.png",
                                  tr("OVERLAY_SETTINGS_PAGE_NL_Overlay_Settings_Title_ST_Tables_Counter").capitalize()),
                                 ("hands", "session/hands_counter_widget.png", tr("SESSION_TIME_PAGE_NL_Hands")),
                                 ("time", "session/widget.png", tr("SESSION_TIME_PAGE_NL_Title_Session_Time"))):
            card = tk.Frame(stats, bg=T.DARK, padx=12, pady=8)
            card.pack(side="left", padx=(0, 10), fill="y")
            tk.Label(card, image=T.image(icon, 30), bg=T.DARK).pack(side="left")
            col = tk.Frame(card, bg=T.DARK)
            col.pack(side="left", padx=(8, 0))
            v = tk.Label(col, text="0", bg=T.DARK, fg="white", font=T.digital(22))
            v.pack(anchor="w")
            tk.Label(col, text=title, bg=T.DARK, fg=T.PRIMARY[200], font=T.font(8, "bold")).pack(anchor="w")
            self.stat_labels[key] = v

        # Sites actifs + layout actif
        mid = tk.Frame(body, bg=T.WINDOW_BG)
        mid.pack(fill="x", pady=(14, 6))
        sites_card = W.Card(mid)
        sites_card.pack(side="left", fill="both", expand=True)
        W.section(sites_card, tr("APP_WINDOW_ACTIVE_SITES_NL_Title_Active_Poker_Sites")).pack(anchor="w")
        self.sites_box = tk.Frame(sites_card, bg=T.WINDOW_BG)
        self.sites_box.pack(fill="x", pady=(6, 0))

        lay_card = W.Card(mid)
        lay_card.pack(side="left", fill="y", padx=(10, 0))
        W.section(lay_card, tr("LAYOUT_CONFIGURATION_NL_Label_Active_Layout")).pack(anchor="w")
        self.layout_var = self.keep(tk.StringVar())
        self.layout_combo = combo(lay_card, self.layout_var, [], 24)
        self.layout_combo.pack(anchor="w", pady=6)
        self.layout_combo.bind("<<ComboboxSelected>>",
                               lambda e: self.app.manager.submit(self.app.manager.switch_layout, self.layout_var.get()))
        btns = tk.Frame(lay_card, bg=T.WINDOW_BG)
        btns.pack(anchor="w")
        W.RoundButton(btns, tr("SETTINGS_NL_Label_Preview_Active_Layout"),
                      lambda: self.app.manager.trigger(Action.PeekActiveLayoutHotKey), kind="secondary",
                      height=30, font_size=9).pack(side="left")
        self.pause_btn = W.RoundButton(btns, "⏸", self._toggle_pause, kind="ghost", height=30, width=40)
        self.pause_btn.pack(side="left", padx=6)
        W.Tooltip(self.pause_btn, "Pause / reprise du placement automatique")

        # Tables gérées
        W.section(body, tr("SETTINGS_NL_Label_Cycle_Through_Tables").split(" dans")[0]).pack(anchor="w", pady=(10, 4))
        cols = ("site", "title", "stakes", "slot", "state")
        tree_box = tk.Frame(body, bg=T.WINDOW_BG)
        tree_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_box, columns=cols, show="headings", selectmode="browse", height=8)
        for c, text, w in zip(cols, ("Site", "Table", "Blinds", "Slot", ""), (110, 360, 80, 160, 140)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=w, anchor="w", stretch=c == "title")
        sb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for kind, color in SLOT_COLORS.items():
            self.tree.tag_configure(kind.value, foreground=color)
        self.tree.tag_configure("action", background=T.RED[50])
        self.empty = tk.Label(body, text=f"{tr('APP_WINDOW_ACTIVE_SITES_NL_Label_No_Sites_Running')} — "
                                         f"{tr('APP_WINDOW_ACTIVE_SITES_NL_Label_Open_Your_Sites_To_Start_Enjoying_Jurojin')}",
                              bg=T.WINDOW_BG, fg=T.TEXT_MUTED, font=T.font(10))

        acts = tk.Frame(body, bg=T.WINDOW_BG)
        acts.pack(fill="x", pady=(8, 0))
        for action, kind in ((Action.SendTableToPlayingArea, "secondary"), (Action.SendTableToObserverArea, "secondary"),
                             (Action.LockTableFromDynamicFlow, "secondary"), (Action.FocusMostUrgentTable, "secondary"),
                             (Action.Ignore, "ghost")):
            W.RoundButton(acts, action_label(action) if action != Action.Ignore else "Ignorer",
                          lambda a=action: self._act(a), kind=kind, height=30, font_size=9).pack(side="left", padx=(0, 6))
        if self.app.backend.name.lower().startswith("simulation"):
            W.RoundButton(acts, "Simuler : action requise", lambda: self._simulate(True), kind="danger", height=30,
                          font_size=9).pack(side="right")
            W.RoundButton(acts, "Simuler : action faite", lambda: self._simulate(False), kind="success", height=30,
                          font_size=9).pack(side="right", padx=6)

    def refresh(self):
        self.refresh_live()

    def refresh_live(self):
        if not self.built:
            return
        m = self.app.manager
        rows = m.snapshot()
        c = m.counters()
        for k in ("tables", "ar", "stacked", "hands"):
            self.stat_labels[k].configure(text=f"{c[k]:02d}")
        self.stat_labels["time"].configure(text=m.session.format_elapsed())
        labels = slot_labels()
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            slot = r["slot"]
            state = "⚠ " + tr("SITE_CONFIGURATION_DETAILS_NL_Label_Action_Required") if r["action"] else ""
            if r["locked"]:
                state += " 🔒"
            if r["in_hand"]:
                state += " In Hand"
            tags = [slot.kind.value] if slot else []
            if r["action"]:
                tags.append("action")
            self.tree.insert("", "end", iid=str(i), values=(
                r["site"], r["title"], r["stakes"],
                f"{labels[slot.kind]} {r['slot_number']}" if slot else "—", state.strip()), tags=tags)
        self._handles = [r["handle"] for r in rows]
        if rows:
            self.empty.pack_forget()
        else:
            self.empty.pack(anchor="w", pady=4, before=self.tree.master)
        # Sites actifs
        for w in self.sites_box.winfo_children():
            w.destroy()
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["site"]] = counts.get(r["site"], 0) + 1
        if not counts:
            tk.Label(self.sites_box, text=tr("APP_WINDOW_ACTIVE_SITES_NL_Label_No_Sites_Running"), bg=T.WINDOW_BG,
                     fg=T.TEXT_MUTED, font=T.font(10, "bold")).pack(anchor="w")
        for name, n in sorted(counts.items()):
            chip = tk.Frame(self.sites_box, bg=T.PRIMARY[50], padx=10, pady=4)
            chip.pack(side="left", padx=(0, 6))
            tk.Label(chip, text=f"♠ {name}", bg=T.PRIMARY[50], fg=T.PRIMARY[800], font=T.font(9, "bold")).pack(side="left")
            tk.Label(chip, text=str(n), bg=T.ACCENT, fg="white", font=T.font(8, "bold"), padx=5).pack(side="left", padx=(6, 0))
        names = [l.name for l in self.cfg.layouts]
        self.layout_combo.configure(values=names)
        self.layout_var.set(self.cfg.active_layout)
        self.pause_btn.set_text("▶" if m.paused else "⏸")

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        i = int(sel[0])
        return self._handles[i] if i < len(self._handles) else None

    def _act(self, action: Action):
        handle = self._selected()
        if action == Action.FocusMostUrgentTable:
            self.app.manager.trigger(action)
        elif handle is not None:
            self.app.manager.trigger(action, handle)

    def _simulate(self, required: bool):
        handle = self._selected()
        if handle is not None:
            self.app.manager.submit(self.app.manager.set_action_required, handle, required)

    def _toggle_pause(self):
        m = self.app.manager
        m.paused = not m.paused
        self.app.notify(f"{APP_NAME} : {'pause' if m.paused else 'actif'}")
        self.refresh_live()
