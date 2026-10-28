"""Configuration Générale : paramètres globaux, alarmes, raccourcis globaux,
bordure de table, langue et fichiers de paramètres (export / import)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog

from ... import i18n, sounds
from ...config import Config
from ...hotkeys import Action
from .. import theme as T
from .. import widgets as W
from . import Page, action_field, action_label, bold, combo, own, radio_group, spin, tr

N = "SETTINGS_NL_"


class SettingsPage(Page):
    title_key = "APP_HAMBURGER_MENU_ITEM_Title_Configuration"

    def build(self):
        self.header(tr(self.title_key), self.app.save, save_text=tr(N + "Button_Save_Changes"))
        bar = self.tabs(self, [tr(N + "Tab_Header_Global_Setting"), tr(N + "Tab_Header_Global_Hotkeys"),
                               tr(N + "Tab_Header_Table_Border"), tr(N + "Button_Settings_File")],
                        [self._tab_global, self._tab_hotkeys, self._tab_border, self._tab_files])
        bar.select(0)

    # ------------------------------------------------------------------ Paramètres globaux
    def _tab_global(self, f):
        g, p = self.cfg.general, self.cfg.placement
        lang = tk.Frame(f, bg=T.WINDOW_BG)
        lang.pack(fill="x", pady=(4, 8))
        bold(lang, tr("WALK_INTRO_LANGUAGE_SELECTION_Label_Choose_Language").capitalize()).pack(side="left", padx=(0, 10))
        self.lang = self.keep(tk.StringVar(value=g.language))
        for code, name in i18n.LANGUAGES.items():
            img = T.image(f"languages/flag-{i18n.FLAGS[code]}.png", 22)
            tk.Radiobutton(lang, image=img, text=" " + name if code == g.language else "", compound="left",
                           variable=self.lang, value=code, indicatoron=False, bg=T.WINDOW_BG, selectcolor=T.PRIMARY[100],
                           relief="flat", offrelief="flat", bd=0, padx=4, pady=2, cursor="hand2",
                           font=T.font(9, "bold"), command=self._change_language).pack(side="left", padx=2)

        rows = (
            ("configuration/magnetize_playing.png", "CheckBox_Magnetize_Playing_Area", p, "magnetize_playing",
             "Tooltip_Body_Magnetize_Playing_Area"),
            ("configuration/magnetize_observer.png", "CheckBox_Magnetize_Observer_Area", p, "magnetize_observer",
             "Tooltip_Body_Magnetize_Observer_Area"),
            ("configuration/magnetize_lobby.png", "CheckBox_Magnetize_Lobby_Slots", p, "magnetize_lobby",
             "Tooltip_Body_Magnetize_Lobby_Slots"),
            ("configuration/invert_ctrl.png", "CheckBox_Invert_Ctrl_Key", p, "invert_ctrl", None),
            ("configuration/reorder_playing.png", "CheckBox_Reorder_Playing_Area_When_Table_Closed", p,
             "reorder_playing_on_close", "Tooltip_Body_Reorder_Playing_Area_When_Table_Closed"),
            ("configuration/reorder_observer.png", "CheckBox_Reorder_Observer_Area_When_Table_Closed", p,
             "reorder_observer_on_close", "Tooltip_Body_Reoder_Observer_Area_When_Table_Closed"),
            ("configuration/most_urgent_on_top.png", "CheckBox_Keep_Most_Urgent_On_Top", p, "stack_urgency",
             "Tooltip_Body_Keep_Most_Urgent_On_Top"),
            ("configuration/auto_focus.png", "CheckBox_Auto_Focus_Most_Urgent_Always", p, "auto_focus_urgent",
             "Tooltip_Body_Auto_Focus_Most_Urgent_Always"),
            ("configuration/force_mouse.png", "CheckBox_Also_Force_Move_Mouse", g, "force_mouse_move",
             "Tooltip_Body_Also_Force_Move_Mouse"),
            ("configuration/focus_under_mouse.png", "CheckBox_Focus_Table_Under_Mouse", g, "focus_follows_mouse",
             "Tooltip_Body_Focus_Table_Under_Mouse"),
            ("configuration/bring_only_tables.png", "CheckBox_Bring_Only_Tables_In_Playing_Slot_To_Front", g,
             "bring_only_playing_to_front", None),
            ("configuration/hide_title.png", "Hide_Title_Bar_Of_Tables", g, "hide_table_titles", None),
            ("configuration/minimize_to_tray.png", "CheckBox_Minimize_App_To_System_Tray", g, "minimize_to_tray",
             "Tooltip_Body_Minimize_Application_To_System_Tray"),
            ("configuration/show_rng.png", "CheckBox_Show_RNG", g, "show_rng", "Tooltip_Body_Show_Random_Number_Generator"),
        )
        for icon, key, obj, attr, tip in rows:
            self.row(f, icon, N + key, obj, attr, N + tip if tip else None)
        W.SettingRow(f, "configuration/drag_table.png", tr(N + "CheckBox_Drag_Table_Clicking_Anywhere"),
                     tk.BooleanVar(value=False), enabled=False,
                     subtitle=own("Non porté : utilisez la barre de titre (la magnétisation reste active).",
                                  "Not ported: use the title bar (magnetization still applies).")).pack(fill="x",
                                                                                                         padx=(0, 12))
        self.separator(f)
        self._alarms(f)
        self.separator(f)
        W.section(f, "Fukuroku").pack(anchor="w")
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=4)
        for text, attr, lo, hi, inc in ((own("Balayage des fenêtres (ms)", "Window scan (ms)"), "poll_interval_ms", 50, 2000, 50),
                                        (own("Délai entre actions (ms)", "Delay between actions (ms)"), "action_delay_ms", 0, 500, 10)):
            W.label(row, text, bold=True).pack(side="left")
            spin(row, self.var(g, attr, int), lo, hi, inc, 6).pack(side="left", padx=(6, 20))
        W.SettingRow(f, None, own("Virgule décimale dans les montants de mise", "Decimal comma in bet amounts"),
                     self.var(g, "decimal_comma")).pack(fill="x", padx=(0, 12))
        W.SettingRow(f, None, own("Démarrer réduit", "Start minimized"), self.var(g, "start_minimized")).pack(fill="x",
                                                                                                           padx=(0, 12))
        W.SettingRow(f, None, own("Prioriser les tables aux plus grosses blinds", "Prioritize higher-stakes tables"),
                     self.var(p, "prioritize_higher_stakes")).pack(fill="x", padx=(0, 12))

    def _alarms(self, f):
        g = self.cfg.general
        names = list(sounds.available())
        for icon, title, en, snd, vol, extra in (
                ("configuration/ar_alarm.png", own("Alarme quand c'est votre tour", "Alarm when it is your turn"),
                 "ar_sound_enabled", "ar_sound", "ar_volume", False),
                ("configuration/delay_ar_alarm.png", tr(N + "Tooltip_Title_Delayed_Alarm_Action_Enabled"),
                 "delayed_alarm_enabled", "delayed_alarm_sound", "delayed_alarm_volume", True)):
            card = W.Card(f)
            card.pack(fill="x", pady=4, padx=(0, 12))
            tip = (title, tr(N + "Tooltip_Body_Delayed_Alarm_Action_Required")) if extra else None
            W.SettingRow(card, icon, title, self.var(g, en), tooltip=tip).pack(fill="x")
            row = tk.Frame(card, bg=T.WINDOW_BG)
            row.pack(anchor="w", padx=56)
            if extra:
                W.label(row, tr("DELAYED_ALARM_FOR_AR_Label_Sounds_After")).pack(side="left")
                spin(row, self.var(g, "delayed_alarm_seconds", int), 1, 120, 1, 4).pack(side="left", padx=4)
                W.label(row, tr("DELAYED_ALARM_FOR_AR_Label_Seconds_Of_Turn_Start"), muted=True).pack(side="left",
                                                                                                    padx=(0, 14))
            sv = self.var(g, snd, str)
            combo(row, sv, names, 12).pack(side="left")
            W.label(row, "  " + tr("DELAYED_ALARM_FOR_AR_Label_Volume")).pack(side="left")
            vv = self.var(g, vol, float)
            tk.Scale(row, from_=0, to=1, resolution=0.05, orient="horizontal", variable=vv, showvalue=False, length=120,
                     bg=T.WINDOW_BG, troughcolor=T.PRIMARY[100], highlightthickness=0, bd=0).pack(side="left", padx=4)
            W.RoundButton(row, "▶", lambda sv=sv, vv=vv: sounds.play(sv.get(), vv.get()), kind="secondary", width=36,
                          height=28).pack(side="left", padx=6)

    def _change_language(self):
        code = self.lang.get()
        if code == self.cfg.general.language:
            return
        self.cfg.general.language = code
        self.app.save(toast=False)
        self.app.current = "settings"
        self.after(10, self.app.rebuild)

    # ------------------------------------------------------------------ Raccourcis globaux
    def _tab_hotkeys(self, f):
        W.banner(f, tr(N + "Info_Hotkeys_Will_Only_Work_Once_You_Leave_This_View")).pack(fill="x", pady=(4, 8),
                                                                                       padx=(0, 12))
        items = ((Action.SwitchLayout, None), (Action.ReorderPlayingArea, N + "Label_Reorder_Playing_Area"),
                 (Action.ReorderObserverArea, N + "Label_Reorder_Observer_Area"),
                 (Action.SendTableToPlayingArea, N + "Label_Send_Table_To_Playing_Area"),
                 (Action.SendTableToObserverArea, N + "Label_Send_Table_To_Observer_Area"),
                 (Action.PeekActiveLayoutHotKey, N + "Label_Preview_Active_Layout"),
                 (Action.CycleHoveredStack, N + "Label_Cycle_Through_Tables"),
                 (Action.DisableAllHotkeys, N + "Label_Disable_All_Hotkeys"),
                 (Action.FocusMostUrgentTable, N + "Label_Focus_Most_Urgent_Table"),
                 (Action.BringNextTableToForeground, N + "Label_Focus_Table_On_Next_Slot"),
                 (Action.BringPreviousTableToForeground, N + "Label_Focus_Table_On_Previous_Slot"),
                 (Action.CloseTable, N + "Label_Close_Table"), (Action.MinimizeTable, N + "Label_Minimize_Table"),
                 (Action.SitoutNextHand, N + "Label_Sitout_Next_Hand"), (Action.SitoutNextBB, N + "Label_Sitout_Next_BB"),
                 (Action.SitOutAtAllTables, N + "Label_Sit_Out_At_All_Tables"),
                 (Action.SitBackIn, N + "Label_Sit_Back_Into_The_Table"), (Action.OpenMenu, None),
                 (Action.ResetMainWindowPosition, None), (Action.OpenNotificationsDebugWindow, None))
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack(fill="x", padx=(0, 12))
        for i, (action, key) in enumerate(items):
            cell = tk.Frame(grid, bg=T.WINDOW_BG, pady=4)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 24))
            W.label(cell, tr(key) if key else action_label(action), bold=True, wrap=260).pack(side="left")
            action_field(cell, self.app, action).pack(side="right")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def refresh(self):
        pass

    def on_tab(self, index: int):
        self.app.hotkeys_suspended = index == 1

    def hide(self):
        self.app.hotkeys_suspended = False

    # ------------------------------------------------------------------ Bordure de table
    def _tab_border(self, f):
        b = self.cfg.border
        card = W.Card(f)
        card.pack(fill="x", pady=(4, 6), padx=(0, 12))
        W.SettingRow(card, "configuration/show_border.png", tr(N + "Check_Show_Border_When_Its_Your_Turn_To_Play"),
                     self.var(b, "enabled")).pack(fill="x")
        mode = self.var(b, "mode", str)
        inner = tk.Frame(card, bg=T.WINDOW_BG)
        inner.pack(anchor="w", padx=56)
        tk.Radiobutton(inner, text=tr(N + "Radio_Use_Color_Transition"), variable=mode, value="transition",
                       bg=T.WINDOW_BG, activebackground=T.WINDOW_BG, selectcolor=T.WINDOW_BG, font=T.font(10, "bold"),
                       highlightthickness=0).pack(anchor="w")
        row = tk.Frame(inner, bg=T.WINDOW_BG)
        row.pack(anchor="w", padx=24)
        tk.Label(row, image=T.image("configuration/color_transition.png", 40), bg=T.WINDOW_BG).pack(side="left")
        W.label(row, tr(N + "Label_The_Color_Will_Gradually_Change_Form_Green_Yellow_To_Red"), muted=True,
                size=9).pack(side="left", padx=6)
        tk.Radiobutton(inner, text=tr(N + "Radio_Choose_Colors"), variable=mode, value="colors", bg=T.WINDOW_BG,
                       activebackground=T.WINDOW_BG, selectcolor=T.WINDOW_BG, font=T.font(10, "bold"),
                       highlightthickness=0).pack(anchor="w", pady=(6, 0))
        row = tk.Frame(inner, bg=T.WINDOW_BG)
        row.pack(anchor="w", padx=24)
        W.label(row, tr(N + "Label_At_The_Start_Of_My_Turn")).pack(side="left")
        self._color_button(row, b, "color_start").pack(side="left", padx=(4, 16))
        W.label(row, tr(N + "Label_In_The_Last_Seconds_Segment1")).pack(side="left")
        spin(row, self.var(b, "last_seconds", int), 1, 60, 1, 4).pack(side="left", padx=4)
        W.label(row, tr(N + "Label_In_The_Last_Seconds_Segment2")).pack(side="left")
        self._color_button(row, b, "color_end").pack(side="left", padx=4)
        row = tk.Frame(inner, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=(6, 0))
        W.label(row, own("Durée d'un tour (s)", "Turn duration (s)"), bold=True).pack(side="left")
        spin(row, self.var(b, "turn_seconds", int), 3, 120, 1, 4).pack(side="left", padx=6)
        for icon, key, attr in (("configuration/blink_border.png", "Check_Blink_Border", "blink"),
                                ("configuration/window_urgent_action.png", "Check_Only_Show_On_Most_Urgent_Table",
                                 "only_most_urgent")):
            W.SettingRow(f, icon, tr(N + key), self.var(b, attr)).pack(fill="x", padx=(0, 12))
        W.SettingRow(f, "configuration/focused_table.png", tr(N + "Check_Highlight_Focused_Table"),
                     self.var(b, "highlight_focused"),
                     control=lambda m: self._with_color(m, b)).pack(fill="x", padx=(0, 12))
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=6)
        tk.Label(row, image=T.image("configuration/border_size.png", 40), bg=T.WINDOW_BG, width=48).pack(side="left")
        bold(row, tr(N + "Label_Border_Size")).pack(side="left", padx=8)
        tk.Scale(row, from_=1, to=12, orient="horizontal", variable=self.var(b, "size", int), length=200,
                 bg=T.WINDOW_BG, troughcolor=T.PRIMARY[100], highlightthickness=0, bd=0).pack(side="left")

    def _with_color(self, master, b):
        fr = tk.Frame(master, bg=T.WINDOW_BG)
        self._color_button(fr, b, "focused_color").pack(side="left", padx=8)
        W.ToggleSwitch(fr, self.var(b, "highlight_focused")).pack(side="left")
        return fr

    def _color_button(self, master, obj, attr: str) -> tk.Label:
        lbl = tk.Label(master, text="    ", bg=getattr(obj, attr), cursor="hand2", relief="solid", bd=1)

        def pick(_e=None):
            color = colorchooser.askcolor(getattr(obj, attr), parent=self)[1]
            if color:
                setattr(obj, attr, color)
                lbl.configure(bg=color)
                self.app.changed()
        lbl.bind("<Button-1>", pick)
        return lbl

    # ------------------------------------------------------------------ Fichiers de paramètres
    def _tab_files(self, f):
        W.label(f, own("Remplace la sauvegarde « cloud » de l'original : tout reste sur votre ordinateur.",
                       "Replaces the original's cloud backup: everything stays on your computer."), muted=True
                ).pack(anchor="w", pady=(4, 10))
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w")
        W.RoundButton(row, tr("EXPORT_SETTINGS_DIALOG_NL_Button_Export_Settings"), self._export).pack(side="left")
        W.RoundButton(row, tr("IMPORT_SETTINGS_DIALOG_NL_Button_Import_Settings"), self._import,
                      kind="secondary").pack(side="left", padx=10)
        W.label(f, str(Config.default_path()), muted=True, size=9).pack(anchor="w", pady=10)

    def _export(self):
        path = filedialog.asksaveasfilename(title=tr("EXPORT_SETTINGS_DIALOG_NL_Title_Export_Settings"),
                                            defaultextension=".zip", filetypes=[("Zip", "*.zip"), ("JSON", "*.json")],
                                            initialfile="fukuroku-settings.zip")
        if path:
            try:
                self.cfg.export_to(Path(path))
                self.app.toast.show(tr("IMPORT_EXPORT_SETTINGS_NL_Status_Success"))
            except OSError as exc:
                W.info(self, tr("IMPORT_EXPORT_SETTINGS_NL_Status_Failure"), str(exc))

    def _import(self):
        path = filedialog.askopenfilename(title=tr("IMPORT_SETTINGS_DIALOG_NL_Title_Import_Settings"),
                                          filetypes=[("Zip / JSON", "*.zip *.json")])
        if not path:
            return
        try:
            new = Config.import_from(Path(path))
        except Exception as exc:
            W.info(self, tr("IMPORT_EXPORT_SETTINGS_NL_Status_Failure"), str(exc))
            return
        # Remplacement en place : le gestionnaire et les pages gardent la même instance.
        for name in vars(new):
            setattr(self.cfg, name, getattr(new, name))
        self.cfg.ensure_layouts(self.app.manager.screens)
        self.app.save(toast=False)
        self.app.manager.submit(self.app.manager.switch_layout, self.cfg.active_layout)
        self.app.current = "settings"
        self.app.toast.show(tr("IMPORT_EXPORT_SETTINGS_NL_Status_Success"))
        self.after(10, self.app.rebuild)
