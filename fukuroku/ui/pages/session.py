"""Temps de Session : minuteur, widgets, notifications et sessions précédentes."""

from __future__ import annotations

import csv
import time
import tkinter as tk
from tkinter import filedialog, ttk

from .. import theme as T
from .. import widgets as W
from . import Page, bold, own, radio_group, spin, tr

S = "SESSION_TIME_PAGE_NL_"


class SessionPage(Page):
    title_key = "SESSION_TIME_PAGE_NL_Title_Session_Time"

    def build(self):
        self.header(tr(self.title_key), self.app.save, save_text=tr(S + "Button_Save_Changes"))
        bar = self.tabs(self, [tr(S + "Switch_Session_Time"), tr(S + "Tab_Header_Session_Widgets"),
                               tr(S + "Tab_Header_Session_Notifications"), tr(S + "Tab_Header_Previous_Sessions")],
                        [self._tab_timer, self._tab_widgets, self._tab_notifications, self._tab_history])
        bar.select(0)

    # ------------------------------------------------------------------ minuteur
    def _tab_timer(self, f):
        s = self.cfg.session
        W.label(f, tr(S + "Tab_Header_Session_Timer"), muted=True, wrap=780).pack(anchor="w", pady=(4, 8))
        self.row(f, "session/widget.png", S + "Switch_Session_Time", s, "timer_enabled")
        self.row(f, "session/manually_use_widget.png", S + "Switch_Show_Session_Timer_Widget", s, "show_timer_widget")
        self.row(f, "session/stop_session.png", S + "Switch_Stop_Session_Timer_Automatically_When_All_Tables_Are_Closed",
                 s, "stop_when_all_closed")
        self.row(f, "session/first_table_opens.png", S + "Switch_Consider_That_I_Have_Closed_All_Tables_After_5_Minutes",
                 s, "closed_grace_5min", subtitle=tr(S + "Label_Ideal_For_Spin_Players"))
        card = W.Card(f)
        card.pack(fill="x", pady=6, padx=(0, 12))
        head = tk.Frame(card, bg=T.WINDOW_BG)
        head.pack(fill="x")
        tk.Label(head, image=T.image("session/start_counting.png", 40), bg=T.WINDOW_BG).pack(side="left")
        bold(head, tr(S + "Label_Start_Counting_Time"), size=11).pack(side="left", padx=10)
        radio_group(card, self.var(s, "start_mode", str), [
            ("first_dealt", tr(S + "Radio_When_I_Am_Dealt_Cards_At_First_Table")),
            ("first_table", tr(S + "Radio_When_First_Table_In_Any_Room_Opens")),
            ("manual", tr(S + "Radio_Manually_Using_Jurojin_Widget"))]).pack(anchor="w", padx=50)
        self.row(f, "session/minimize_session.png", S + "Label_Minimize_The_Session_Time_Widget_When_Starting_The_Timer",
                 s, "minimize_widget_on_start")
        g = self.cfg.general
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=8)
        bold(row, own("Rappel de pause toutes les", "Break reminder every")).pack(side="left")
        spin(row, self.var(g, "break_every_min", int), 0, 600, 5, 5).pack(side="left", padx=6)
        W.label(row, own("minutes (0 = jamais)", "minutes (0 = never)"), muted=True).pack(side="left")
        W.SettingRow(f, None, own("Journal CSV des sessions", "CSV session log"), self.var(g, "session_log"),
                     subtitle=own("sessions.csv dans le dossier de configuration",
                                  "sessions.csv in the configuration folder")).pack(fill="x", padx=(0, 12))

    # ------------------------------------------------------------------ widgets
    def _tab_widgets(self, f):
        s = self.cfg.session
        for icon, key, attr in (("session/slot_tables_widget.png", "Label_Show_Open_Tables_Counter_Widget",
                                 "show_open_tables_widget"),
                                ("session/ar_tables_widget.png", "Label_Show_Ar_Tables_Widget", "show_ar_tables_widget"),
                                ("session/hands_counter_widget.png", "Label_Show_Hands_Played_Widget",
                                 "show_hands_widget")):
            card = W.Card(f)
            card.pack(fill="x", pady=4, padx=(0, 12))
            W.SettingRow(card, icon, tr(S + key), self.var(s, attr), subtitle=tr(S + "Label_Show_Widget")).pack(fill="x")
        card = W.Card(f)
        card.pack(fill="x", pady=4, padx=(0, 12))
        bold(card, tr(S + "Label_Count_Specific_Type")).pack(anchor="w")
        radio_group(card, self.var(s, "count_type", str), [
            ("all", tr(S + "Option_Count_All_Tables")), ("spin", tr(S + "Option_Count_Spin_Tables_Only")),
            ("tournament", tr(S + "Option_Count_Tournament_Tables_Only")),
            ("cash", tr(S + "Option_Count_Cash_Tables_Only"))], vertical=False).pack(anchor="w")
        illus = tk.Frame(f, bg=T.WINDOW_BG)
        illus.pack(anchor="w", pady=8)
        for img in ("session/slot_tables_illustator.png", "session/ar_tables_illustator.png",
                    "session/hands_played_illustator.png"):
            tk.Label(illus, image=T.image(img, 200), bg=T.WINDOW_BG).pack(side="left", padx=(0, 12))

    # ------------------------------------------------------------------ notifications
    def _tab_notifications(self, f):
        s = self.cfg.session
        for icon, en, attr, label, unit in (
                ("session/notify_after_played.png", "notify_hands_enabled", "notify_hands",
                 "Label_Notify_Me_After_I_Have_Played", "Label_Hands"),
                ("session/notify_after_opened.png", "notify_tables_enabled", "notify_tables",
                 "Label_Notify_Me_After_I_Have_Opened", "Label_Tables")):
            card = W.Card(f)
            card.pack(fill="x", pady=4, padx=(0, 12))

            def control(m, attr=attr, unit=unit):
                fr = tk.Frame(m, bg=T.WINDOW_BG)
                spin(fr, self.var(s, attr, int), 1, 100000, 10, 7).pack(side="left")
                W.label(fr, " " + tr(S + unit)).pack(side="left", padx=(0, 10))
                W.ToggleSwitch(fr, self.var(s, en)).pack(side="left")
                return fr
            W.SettingRow(card, icon, tr(S + label), control=control).pack(fill="x")
        tk.Label(f, image=T.image("session/notify_me.png", 120), bg=T.WINDOW_BG).pack(anchor="w", pady=10)

    # ------------------------------------------------------------------ sessions précédentes
    def _tab_history(self, f):
        filt = tk.Frame(f, bg=T.WINDOW_BG)
        filt.pack(fill="x", pady=(4, 6))
        bold(filt, tr(S + "Label_Filters")).pack(side="left")
        self.d_from = self.keep(tk.StringVar())
        self.d_to = self.keep(tk.StringVar())
        for key, v in (("Label_From", self.d_from), ("Label_To", self.d_to)):
            W.label(filt, "  " + tr(S + key)).pack(side="left")
            ttk.Entry(filt, textvariable=v, width=11).pack(side="left", padx=4)
            v.trace_add("write", lambda *_: self._fill())
        W.label(filt, "(AAAA-MM-JJ)", muted=True, size=8).pack(side="left")
        W.RoundButton(filt, tr(S + "Button_Reset"), lambda: (self.d_from.set(""), self.d_to.set("")), kind="ghost",
                      height=28, font_size=9).pack(side="left", padx=8)
        W.RoundButton(filt, tr(S + "Button_Clear_Sessions"), self._clear, kind="danger", height=28,
                      font_size=9).pack(side="right", padx=(0, 12))
        W.RoundButton(filt, "CSV", self._export, kind="secondary", height=28, width=60,
                      font_size=9).pack(side="right", padx=6)
        cols = ("date", "duration", "tables", "max", "hands", "actions")
        box = tk.Frame(f, bg=T.WINDOW_BG)
        box.pack(fill="both", expand=True, padx=(0, 12))
        self.tree = ttk.Treeview(box, columns=cols, show="headings", height=14)
        for c, text in zip(cols, (tr(S + "Label_Date"), tr(S + "Duration"), tr(S + "Open_Tables"),
                                  own("Max simultanées", "Max at once"), tr(S + "Hands"), tr(S + "Actions"))):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=120, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.total = bold(f, "")
        self.total.pack(anchor="w", pady=6)
        self._fill()

    def _rows(self) -> list[dict]:
        def ts(text: str, end: bool):
            try:
                return time.mktime(time.strptime(text.strip(), "%Y-%m-%d")) + (86399 if end else 0)
            except ValueError:
                return None
        return self.app.history.filtered(ts(self.d_from.get(), False), ts(self.d_to.get(), True))

    def _fill(self):
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        rows = self._rows()
        for r in reversed(rows):
            d = int(r.get("duration_s", 0))
            self.tree.insert("", "end", values=(r.get("date", ""), f"{d // 3600:02d}:{d % 3600 // 60:02d}:{d % 60:02d}",
                                                r.get("tables", 0), r.get("max_tables", 0), r.get("hands", 0),
                                                r.get("actions", 0)))
        if not rows:
            self.total.configure(text=tr(S + "Label_No_Sessions_Saved"))
        else:
            d = sum(int(r.get("duration_s", 0)) for r in rows)
            self.total.configure(text=f"Σ  {len(rows)} sessions — {d // 3600} h {d % 3600 // 60:02d} — "
                                      f"{sum(int(r.get('hands', 0)) for r in rows)} {tr(S + 'Label_Hands')}")

    def _clear(self):
        if W.ask_yes_no(self, tr(S + "DIALOG_DELETE_SESSION_Title"), tr(S + "DIALOG_DELETE_SESSION_Title") + " ?",
                        tr("DIALOG_DELETE_LAYOUT_NL_Button_Delete"), tr("DIALOG_DELETE_LAYOUT_NL_Button_Cancel"),
                        danger=True):
            self.app.history.clear()
            self._fill()

    def _export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "duration_s", "tables", "max_tables", "hands", "actions"])
            for r in self._rows():
                w.writerow([r.get(k, "") for k in ("date", "duration_s", "tables", "max_tables", "hands", "actions")])
        self.app.toast.show(path)

    def refresh(self):
        self._fill()
