"""Overlays pour Tables : overlays attachés aux tables, compteurs flottants et RNG."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from ...hotkeys import Action
from .. import theme as T
from .. import widgets as W
from . import NEEDS_DATA, Page, action_field, bold, own, radio_group, spin, tr

O = "OVERLAY_SETTINGS_PAGE_NL_"


class OverlaysPage(Page):
    title_key = "APP_HAMBURGER_MENU_ITEM_Title_Overlays"

    def build(self):
        self.header(tr(self.title_key), self.app.save, save_text=tr(O + "Button_Save_Changes"))
        bar = self.tabs(self, [tr(O + "Tab_Header_Table_Overlays"), tr(O + "Tab_Header_Table_Counters"),
                               tr(O + "RNG_Title")], [self._tab_table, self._tab_counters, self._tab_rng])
        bar.select(0)

    def _card(self, f, icon: str | None, title: str, attr: str | None, enabled: bool = True) -> tk.Frame:
        o = self.cfg.overlays
        card = W.Card(f)
        card.pack(fill="x", pady=4, padx=(0, 12))
        if attr:
            W.SettingRow(card, icon, title, self.var(o, attr), enabled=enabled).pack(fill="x")
        else:
            W.SettingRow(card, icon, title).pack(fill="x")
        return card

    # ------------------------------------------------------------------ Superpositions de table
    def _tab_table(self, f):
        o = self.cfg.overlays
        gen = tk.Frame(f, bg=T.WINDOW_BG)
        gen.pack(fill="x", pady=(4, 6))
        bold(gen, tr(O + "Label_Size")).pack(side="left")
        radio_group(gen, self.var(o, "size", str), [("small", tr(O + "Label_Small")), ("medium", tr(O + "Label_Medium")),
                                                    ("big", tr(O + "Label_Big"))], vertical=False).pack(side="left", padx=10)
        bold(gen, tr(O + "Label_Opacity")).pack(side="left", padx=(20, 4))
        tk.Scale(gen, from_=0.3, to=1.0, resolution=0.05, orient="horizontal", variable=self.var(o, "opacity", float),
                 showvalue=False, length=140, bg=T.WINDOW_BG, troughcolor=T.PRIMARY[100], highlightthickness=0,
                 bd=0).pack(side="left")
        self.row(f, "overlay/alt_key.png", O + "Label_Move_Overlays_Only_When_Holding_Ctrl", o, "move_with_ctrl")

        card = self._card(f, "hotkey/overlay.png", tr(O + "Overlay_Settings_Title_Bet_Buttons").capitalize(), "bet_buttons")
        row = tk.Frame(card, bg=T.WINDOW_BG)
        row.pack(anchor="w", padx=56)
        bold(row, tr(O + "Bet_Buttons_Label_Buttons")).pack(side="left")
        radio_group(row, self.var(o, "bet_buttons_count", int), [(4, tr(O + "Bet_Buttons_Buttons_Option_4_Buttons")),
                                                                (8, tr(O + "Bet_Buttons_Buttons_Option_8_Buttons"))],
                    vertical=False).pack(side="left", padx=10)
        go = tk.Label(row, text=tr(O + "Label_Set_Sizes_For_This_Overlay_In_Hotkeys_Section") + "  ›", bg=T.WINDOW_BG,
                      fg=T.ACCENT, font=T.font(9, "bold"), cursor="hand2")
        go.pack(side="left", padx=10)
        go.bind("<Button-1>", lambda e: self.app.show_page("hotkeys"))
        for key, attr in (("Label_Convert_The_Last_Bet_Button_Into_An_All_In_Max", "bet_buttons_last_allin"),
                          ("Label_Keep_Bet_Buttons_Visible_Even_When_Its_Not_Hero_Turn", "bet_buttons_always_visible")):
            W.SettingRow(card, None, tr(O + key), self.var(o, attr)).pack(fill="x", padx=(56, 0))

        card = self._card(f, "overlay/customization.png", tr(O + "Overlay_Settings_Title_Take_Screenshot").capitalize(),
                          "screenshot")
        row = tk.Frame(card, bg=T.WINDOW_BG)
        row.pack(anchor="w", padx=56)
        folder = self.var(o, "screenshot_folder", str)
        ttk.Entry(row, textvariable=folder, width=50).pack(side="left")
        W.RoundButton(row, "…", lambda: folder.set(filedialog.askdirectory() or folder.get()), kind="ghost",
                      height=28, width=36).pack(side="left", padx=6)

        W.section(f, own("Overlays de données", "Data overlays")).pack(anchor="w", pady=(10, 2))
        has = self.app.manager.data_provider is not None
        if not has:
            W.banner(f, own(*NEEDS_DATA), kind="warning").pack(fill="x", pady=4, padx=(0, 12))
        for key, attr in (("Overlay_Settings_Title_Pot_Odds", "pot_odds"), ("Pot_Odds_Display_As_Option_Check_Ratio", "pot_odds_ratio"),
                          ("Overlay_Settings_Title_Stack_To_Pot_Ratio", "spr"),
                          ("Overlay_Settings_Title_Effective_Stack", "effs"),
                          ("Overlay_Settings_Title_Minimum_Defense_Frequency", "mdf"),
                          ("Overlay_Settings_Title_Bluff_Equity", "bluff_equity"),
                          ("Overlay_Settings_Title_Minimum_Outs", "outs"),
                          ("Overlay_Settings_Title_SPR_Next_Street", "spr_next_street"),
                          ("Overlay_Settings_Title_POT_Next_Street", "pot_next_street"),
                          ("Overlay_Settings_Title_Position", "positions"),
                          ("Overlay_Settings_Title_Action_History", "action_history")):
            W.SettingRow(f, None, tr(O + key).capitalize(), self.var(o, attr), enabled=has).pack(fill="x", padx=(0, 12))
        tk.Label(f, image=T.image("overlay/preview/cards.png", 220), bg=T.WINDOW_BG).pack(anchor="w", pady=8)

    # ------------------------------------------------------------------ Compteurs de table
    def _tab_counters(self, f):
        o = self.cfg.overlays
        for icon, key, attr, name in (("overlay/ar_table.png", "Overlay_Settings_Title_AR_Tables_Counter", "ar_counter",
                                       "ar_counter"),
                                      ("overlay/st_table.png", "Overlay_Settings_Title_ST_Tables_Counter", "st_counter",
                                       "st_counter")):
            card = W.Card(f)
            card.pack(fill="x", pady=4, padx=(0, 12))
            W.SettingRow(card, icon, tr(O + key).capitalize(), self.var(o, attr)).pack(fill="x")
        W.label(f, own("Les compteurs sont des fenêtres flottantes : déplacez-les à la souris, leur position est "
                       "mémorisée.", "Counters are floating windows: drag them, their position is remembered."),
                muted=True, size=9).pack(anchor="w", pady=6)
        W.RoundButton(f, tr(O + "Button_Reset_Positions_To_Default"), self._reset_positions, kind="secondary",
                      icon="overlay/reset.png").pack(anchor="w")

    def _reset_positions(self):
        self.cfg.session.widget_positions.clear()
        for name in list(self.app.floating):
            if name != "rng":
                self.app.reset_widget(name)
        self.app.changed()

    # ------------------------------------------------------------------ RNG
    def _tab_rng(self, f):
        r, g = self.cfg.rng, self.cfg.general
        self.row(f, "configuration/show_rng.png", "SETTINGS_NL_CheckBox_Show_RNG", g, "show_rng",
                 "SETTINGS_NL_Tooltip_Body_Show_Random_Number_Generator", subtitle=tr("SETTINGS_NL_CheckBox_Sub_Show_RNG"))
        card = W.Card(f)
        card.pack(fill="x", pady=6, padx=(0, 12))
        row = tk.Frame(card, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=2)
        bold(row, tr(O + "RNG_Label_Range")).pack(side="left", padx=(0, 8))
        spin(row, self.var(r, "minimum", int, self._rng_changed), 0, 9999, 1, 6).pack(side="left")
        W.label(row, f"  {tr(O + 'RNG_Label_To')}  ").pack(side="left")
        spin(row, self.var(r, "maximum", int, self._rng_changed), 1, 9999, 1, 6).pack(side="left")
        bold(card, tr(O + "RNG_Label_Roll_On")).pack(anchor="w", pady=(8, 0))
        radio_group(card, self.var(r, "roll_on", str, self._rng_changed), [
            ("time", tr(O + "RNG_Radio_RollOn_Time")), ("my_turn", tr(O + "RNG_Radio_RollOn_My_Turn")),
            ("hand", tr(O + "RNG_Radio_RollOn_Hand"))], vertical=False).pack(anchor="w")
        row = tk.Frame(card, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=(8, 2))
        bold(row, tr(O + "RNG_Label_Refresh_After")).pack(side="left", padx=(0, 8))
        spin(row, self.var(r, "interval_s", float, self._rng_changed), 0.5, 600, 0.5, 6).pack(side="left")
        W.label(row, "  " + tr(O + "RNG_Label_Seconds")).pack(side="left")
        row = tk.Frame(card, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=(8, 2))
        bold(row, tr(O + "Label_Opacity")).pack(side="left", padx=(0, 8))
        tk.Scale(row, from_=0.3, to=1.0, resolution=0.05, orient="horizontal",
                 variable=self.var(r, "opacity", float, self._rng_changed), showvalue=False, length=160,
                 bg=T.WINDOW_BG, troughcolor=T.PRIMARY[100], highlightthickness=0, bd=0).pack(side="left")
        W.SettingRow(f, "overlay/bring_forward.png", tr("RNG_SETTINGS_Label_Move_To_Mouse_Pointer"),
                     control=lambda m: action_field(m, self.app, Action.RNGMoveToPointer)).pack(fill="x", padx=(0, 12))
        W.label(f, own("Clic droit ou double-clic sur le RNG : nouveau tirage.", "Right-click or double-click the "
                       "RNG: new draw."), muted=True, size=9).pack(anchor="w", pady=4)

    def _rng_changed(self):
        if "rng" in self.app.floating:
            self.app.reset_widget("rng")
