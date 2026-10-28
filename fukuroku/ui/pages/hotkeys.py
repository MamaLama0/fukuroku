"""Raccourcis Clavier : boutons de mise (16), paramètres d'envoi et liste complète."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...betsizing import BetButton
from ...gamepad import GAMEPAD_BUTTONS
from ...hotkeys import Action
from .. import theme as T
from .. import widgets as W
from . import Page, action_field, action_label, bold, combo, format_hotkey, own, radio_group, tr

H = "HOTKEYS_NL_"


class HotkeysPage(Page):
    title_key = "HOTKEYS_NL_Title_Table_Hotkeys"

    def build(self):
        self.header(tr(self.title_key), self.app.save, save_text=tr(H + "Button_Save_Changes"))
        hs = self.cfg.hotkey_settings
        while len(hs.bet_buttons) < 16:
            hs.bet_buttons.append(BetButton())
        self.tabbar = bar = self.tabs(self, [tr(H + "Tab_Header_Bet_Buttons"), tr(H + "Tab_Header_Hotkey_Configuration"),
                               own("Tous les raccourcis", "All hotkeys")],
                        [self._tab_bets, self._tab_settings, self._tab_all])
        bar.select(0)

    def hide(self):
        self.app.hotkeys_suspended = False  # « les raccourcis ne fonctionneront qu'une fois cette vue quittée »

    # ------------------------------------------------------------------ Boutons de mise
    def _tab_bets(self, f):
        W.banner(f, tr(H + "Label_The_Hotkeys_Will_Only_Work_Once_You_Leave_This_View")).pack(fill="x", pady=(4, 8),
                                                                                           padx=(0, 12))
        actions = tk.Frame(f, bg=T.WINDOW_BG)
        actions.pack(anchor="w")
        for i, (action, key) in enumerate(((Action.Fold, "Label_Fold"), (Action.Check, "Label_Check_Call"),
                                           (Action.BetRaise, "Label_Bet_Raise"), (Action.AllIn, "Label_All_In"),
                                           (Action.Increment, "Label_Increment"), (Action.Decrement, "Label_Decrement"))):
            cell = tk.Frame(actions, bg=T.DARK, padx=10, pady=8)
            cell.grid(row=0, column=i, padx=(0, 6), pady=4, sticky="nsew")
            tk.Label(cell, text=tr(H + key), bg=T.DARK, fg="white", font=T.font(9, "bold")).pack(anchor="w")
            action_field(cell, self.app, action, width=11).pack(anchor="w", pady=(4, 0))

        hs = self.cfg.hotkey_settings
        legend = tk.Frame(f, bg=T.WINDOW_BG)
        legend.pack(anchor="w", pady=(12, 2))
        for key, sub in (("Label_Preflop_Bet", "Label_Big_Blind_Or_Button_Blind"),
                         ("Label_Normal_Bet_Size", "Label_Percent_Of_Pot"),
                         ("Label_Previous_Bet_Multiplier", "X_Times_Previous_Bet_Raise")):
            col = tk.Frame(legend, bg=T.WINDOW_BG)
            col.pack(side="left", padx=(0, 22))
            bold(col, tr(H + key), fg=T.PRIMARY[700]).pack(anchor="w")
            W.label(col, tr(H + sub), muted=True, size=8).pack(anchor="w")
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack(anchor="w", pady=4)
        for i, btn in enumerate(hs.bet_buttons[:16], start=1):
            cell = tk.Frame(grid, bg=T.GRAY[50], padx=10, pady=8, highlightthickness=1, highlightbackground=T.BORDER)
            cell.grid(row=(i - 1) // 4, column=(i - 1) % 4, padx=4, pady=4, sticky="nsew")
            top = tk.Frame(cell, bg=T.GRAY[50])
            top.pack(fill="x")
            tk.Label(top, image=T.image("hotkey/btn1.png", 18), bg=T.GRAY[50]).pack(side="left")
            bold(top, tr(f"{H}Label_Button{i}"), bg=T.GRAY[50], fg=T.PRIMARY[800]).pack(side="left", padx=4)
            action_field(cell, self.app, Action(f"Button{i}"), bg=T.GRAY[50], width=18).pack(anchor="w", pady=4)
            vals = tk.Frame(cell, bg=T.GRAY[50])
            vals.pack(anchor="w")
            for attr, suffix in (("preflop_bb", "bb"), ("postflop_pct", "%"), ("multiplier", "x")):
                self._float_entry(vals, btn, attr).pack(side="left")
                tk.Label(vals, text=suffix, bg=T.GRAY[50], fg=T.TEXT_MUTED, font=T.font(8)).pack(side="left", padx=(1, 6))
            geo = self.keep(tk.BooleanVar(value=btn.geometric))
            geo.trace_add("write", lambda *_, b=btn, g=geo: (setattr(b, "geometric", g.get()), self.app.changed()))
            tk.Checkbutton(cell, text=tr(H + "Label_Geometric_Betsizing"), variable=geo, bg=T.GRAY[50],
                           activebackground=T.GRAY[50], font=T.font(8), selectcolor=T.WINDOW_BG,
                           highlightthickness=0).pack(anchor="w")
        W.label(f, W.strip_html(tr("CONFIG_BET_SIZE_Help_If_You_Leave_The_One_Of_The_Betsizes_Multiplier_Jurojin_Will_Use_The_Bb")),
                muted=True, size=8, wrap=760).pack(anchor="w", pady=(4, 0))

        rm = hs.raise_mode
        card = W.Card(f)
        card.pack(fill="x", pady=10, padx=(0, 12))
        W.section(card, tr("CONFIG_RAISE_MODE_Title")).pack(anchor="w")
        cols = tk.Frame(card, bg=T.WINDOW_BG)
        cols.pack(anchor="w", pady=4)
        c1 = tk.Frame(cols, bg=T.WINDOW_BG)
        c1.pack(side="left", padx=(0, 40), anchor="n")
        bold(c1, tr("CONFIG_RAISE_MODE_Label_When_Facing_A_Bet_Raise_Prefop")).pack(anchor="w")
        radio_group(c1, self.var(rm, "preflop", str), [
            ("bb", tr("CONFIG_RAISE_MODE_Radio_When_Preflop_Use_BB")),
            ("psb", tr("CONFIG_RAISE_MODE_Radio_When_Preflop_Use_PSB")),
            ("times", tr("CONFIG_RAISE_MODE_Radio_When_Preflop_Use_Times_Bet"))]).pack(anchor="w")
        c2 = tk.Frame(cols, bg=T.WINDOW_BG)
        c2.pack(side="left", anchor="n")
        bold(c2, tr("CONFIG_RAISE_MODE_Label_When_Facing_A_Bet_Raise_Postflop")).pack(anchor="w")
        radio_group(c2, self.var(rm, "postflop", str), [
            ("psb", tr("CONFIG_RAISE_MODE_Radio_When_Postflop_Use_PSB")),
            ("times", tr("CONFIG_RAISE_MODE_Radio_When_Postflop_Use_Multiplier"))]).pack(anchor="w")
        self.row(f, "hotkey/ctrl_key.png", H + "Label_Use_Ctrl_Key_To_Switch_Between_Button_Groups", hs,
                 "ctrl_switches_groups")

    def _float_entry(self, parent, obj, attr: str) -> ttk.Entry:
        value = getattr(obj, attr)
        v = self.keep(tk.StringVar(value="" if value is None else f"{value:g}"))

        def write(*_):
            text = v.get().strip().replace(",", ".")
            try:
                setattr(obj, attr, float(text) if text else None)
            except ValueError:
                return
            self.app.changed()
        v.trace_add("write", write)
        return ttk.Entry(parent, textvariable=v, width=5)

    # ------------------------------------------------------------------ Paramètres
    def _tab_settings(self, f):
        hs = self.cfg.hotkey_settings
        card = W.Card(f)
        card.pack(fill="x", pady=(4, 6), padx=(0, 12))
        head = tk.Frame(card, bg=T.WINDOW_BG)
        head.pack(fill="x")
        tk.Label(head, image=T.image("hotkey/below_pointer.png", 40), bg=T.WINDOW_BG).pack(side="left")
        bold(head, tr(H + "Label_Send_The_Hotkey_To"), size=11).pack(side="left", padx=10)
        radio_group(card, self.var(hs, "target", str), [("hovered", tr(H + "Check_Table_Below_Mouse_Pointer")),
                                                        ("focused", tr(H + "Check_Focused_Table"))],
                    vertical=False).pack(anchor="w", padx=50, pady=4)

        card = W.Card(f)
        card.pack(fill="x", pady=6, padx=(0, 12))
        W.SettingRow(card, "hotkey/increment_decrement.png", tr(H + "Label_Override_Poker_Site_Wheel_Betting"),
                     self.var(hs, "wheel_betting"),
                     subtitle=f"{format_hotkey('wheel_up')} / {format_hotkey('wheel_down')} → "
                              f"{action_label(Action.IncreaseBet)} / {action_label(Action.DecreaseBet)}").pack(fill="x")
        steps = tk.Frame(card, bg=T.WINDOW_BG)
        steps.pack(anchor="w", padx=56)
        step = self.var(hs, "wheel_step", str)
        for value, key, icon in (("sb", "Label_Small_Blinds", "hotkey/small_blinds.png"),
                                 ("bb", "Label_Big_Blinds", "hotkey/big_blinds.png")):
            tk.Radiobutton(steps, text=" " + tr(H + key), image=T.image(icon, 26), compound="left", variable=step,
                           value=value, bg=T.WINDOW_BG, activebackground=T.WINDOW_BG, selectcolor=T.WINDOW_BG,
                           font=T.font(10), highlightthickness=0).pack(side="left", padx=(0, 20))

        card = W.Card(f)
        card.pack(fill="x", pady=6, padx=(0, 12))
        W.section(card, tr(H + "Label_AutoBet")).pack(anchor="w")
        for icon, key, attr in (("hotkey/instanly_shove.png", "Label_Instantly_Shove_Bet_When_Pressing_Hotkey",
                                 "instant_shove_hotkey"),
                                ("hotkey/overlay.png", "Label_Also_Instantly_Shove_When_Using_Betting_Overlay",
                                 "instant_shove_overlay"),
                                ("hotkey/allin_insta.png", "Label_Instant_Shove_Only_All_In", "instant_shove_allin_only")):
            W.SettingRow(card, icon, W.strip_html(tr(H + key)), self.var(hs, attr)).pack(fill="x")

        card = W.Card(f)
        card.pack(fill="x", pady=6, padx=(0, 12))
        W.SettingRow(card, "hotkey/toggle_bb_mode.png", tr(H + "Label_Toggle_BB_Mode"),
                     control=lambda m: action_field(m, self.app, Action.ToggleBBMode)).pack(fill="x")
        W.SettingRow(card, "hotkey/focused_table.png", action_label(Action.FocusMostUrgentTable),
                     control=lambda m: action_field(m, self.app, Action.FocusMostUrgentTable)).pack(fill="x")

    # ------------------------------------------------------------------ Tous les raccourcis
    def _tab_all(self, f):
        W.label(f, own("Double-clic : définir le raccourci clavier/souris.  Colonne manette : choisir un bouton.",
                       "Double-click: set the keyboard/mouse hotkey.  Controller column: pick a button."),
                muted=True, size=9).pack(anchor="w", pady=(4, 6))
        box = tk.Frame(f, bg=T.WINDOW_BG)
        box.pack(fill="both", expand=True, padx=(0, 12))
        self.tree = ttk.Treeview(box, columns=("action", "hotkey", "gamepad"), show="headings", height=16)
        for c, text, w in (("action", "Action", 380), ("hotkey", own("Raccourci", "Hotkey"), 180),
                           ("gamepad", tr("APP_HAMBURGER_MENU_ITEM_Title_Controller"), 160)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", lambda e: self._edit_selected())
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=8)
        W.RoundButton(row, own("Définir", "Set"), self._edit_selected, kind="secondary", height=30,
                      font_size=9).pack(side="left")
        W.RoundButton(row, own("Effacer", "Clear"), self._clear_selected, kind="ghost", height=30,
                      font_size=9).pack(side="left", padx=6)
        bold(row, "  " + tr("APP_HAMBURGER_MENU_ITEM_Title_Controller") + " :").pack(side="left")
        self.pad_var = self.keep(tk.StringVar())
        cb = combo(row, self.pad_var, ["—"] + GAMEPAD_BUTTONS, 26)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._set_gamepad())
        self._fill_tree()

    def _fill_tree(self):
        if not hasattr(self, "tree"):
            return
        reg = self.cfg.hotkeys
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for action in Action:
            b = reg.bindings.get(action)
            self.tree.insert("", "end", iid=action.value, values=(
                action_label(action), format_hotkey(b.hotkey) if b and b.hotkey else "",
                b.gamepad if b and b.gamepad else ""))
        if sel:
            self.tree.selection_set(sel)

    def _selected_action(self) -> Action | None:
        sel = self.tree.selection()
        return Action(sel[0]) if sel else None

    def _edit_selected(self):
        action = self._selected_action()
        if action is None:
            return
        b = self.cfg.hotkeys.bindings.get(action)
        self.app.capture_hotkey(action_label(action), b.hotkey if b else None,
                                lambda hk: self.app.bind_action(action, hk) and self._fill_tree())

    def _clear_selected(self):
        action = self._selected_action()
        if action is not None:
            self.app.bind_action(action, None)
            self.cfg.hotkeys.bind_gamepad(action, None)
            self._fill_tree()

    def _set_gamepad(self):
        action = self._selected_action()
        if action is None:
            return
        button = self.pad_var.get()
        try:
            self.cfg.hotkeys.bind_gamepad(action, None if button == "—" else button)
        except ValueError as exc:
            W.info(self, tr("APP_HAMBURGER_MENU_ITEM_Title_Controller"), str(exc))
            return
        self.app.changed()
        self._fill_tree()

    def refresh(self):
        self.app.hotkeys_suspended = True
        self._fill_tree()
