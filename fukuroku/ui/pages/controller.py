"""Contrôleur : détection de la manette, vibration, vitesse du curseur, correspondances."""

from __future__ import annotations

import tkinter as tk

from .. import theme as T
from .. import widgets as W
from . import Page, bold, own, tr

C = "CONTROLLER_PAGE_NL_"

# Correspondances d'origine affichées autour de la manette (bouton → libellé).
_LEFT = (("LeftTrigger", "Label_All_In"), ("LeftButton", "Label_Decrement_Bet"), ("LeftThumbPress", "Label_Press_To_Show_Cursor"),
         ("DPadUp / DPadDown", "Label_Cycle_Through_Stacked_Tables"), ("DPadLeft / DPadRight", "Label_Change_Selected_Table"),
         ("Select", "Label_Toggle_BB_Mode"))
_RIGHT = (("RightTrigger", "Label_Bet_Raise"), ("RightButton", "Label_Increment_Bet"), ("Y", "Label_Go_To_Most_Urgent"),
          ("X", "Label_Fold"), ("A", "Label_Check_Call"), ("B", "Label_Quick_Actions_Menu"),
          ("RightThumb", "Label_Moves_And_Swaps_The_Tables"))


class ControllerPage(Page):
    title_key = "CONTROLLER_PAGE_NL_Title_Controller_Support"

    def build(self):
        self.header(tr(self.title_key), self.app.save)
        c = self.cfg.controller
        body = tk.Frame(self, bg=T.WINDOW_BG)
        body.pack(fill="both", expand=True, padx=28)
        top = tk.Frame(body, bg=T.WINDOW_BG)
        top.pack(fill="x")
        status = W.Card(top)
        status.pack(side="left", fill="y")
        self.state_img = tk.Label(status, bg=T.WINDOW_BG)
        self.state_img.pack()
        self.state_lbl = bold(status, "", size=11)
        self.state_lbl.pack(pady=4)
        self.btn = W.RoundButton(status, tr(C + "Button_Detect_Controller"), self._toggle, width=210)
        self.btn.pack(pady=(4, 0))
        opts = tk.Frame(top, bg=T.WINDOW_BG)
        opts.pack(side="left", fill="both", expand=True, padx=(16, 0))
        W.banner(opts, tr(C + "Label_The_Controller_Will_Use_Betsizes_You_Configure_On_Hotkeys_Section")).pack(fill="x")
        W.SettingRow(opts, "controller/vibrate_controller.png", tr(C + "Label_Vibrate_When_Its_My_Turn_To_Play"),
                     self.var(c, "vibrate_on_turn")).pack(fill="x")
        sp = tk.Frame(opts, bg=T.WINDOW_BG)
        sp.pack(fill="x", pady=4)
        tk.Label(sp, image=T.image("controller/cursor.png", 40), bg=T.WINDOW_BG, width=48).pack(side="left")
        col = tk.Frame(sp, bg=T.WINDOW_BG)
        col.pack(side="left", fill="x", expand=True, padx=8)
        bold(col, tr(C + "Label_Press_To_Show_Cursor")).pack(anchor="w")
        W.label(col, tr(C + "Label_You_Can_Press_The_Analog_Stick_To_Make_Juro_Cursor_Appear"), muted=True, size=9,
                wrap=520).pack(anchor="w")
        scale_row = tk.Frame(col, bg=T.WINDOW_BG)
        scale_row.pack(anchor="w")
        W.label(scale_row, tr(C + "Label_Really_Slow"), muted=True, size=8).pack(side="left")
        tk.Scale(scale_row, from_=1, to=10, orient="horizontal", variable=self.var(c, "cursor_speed", int),
                 showvalue=False, length=220, bg=T.WINDOW_BG, troughcolor=T.PRIMARY[100], highlightthickness=0,
                 activebackground=T.ACCENT, bd=0).pack(side="left", padx=6)
        W.label(scale_row, tr(C + "Label_Super_Fast"), muted=True, size=8).pack(side="left")

        mapping = tk.Frame(body, bg=T.WINDOW_BG)
        mapping.pack(fill="both", expand=True, pady=10)
        left = tk.Frame(mapping, bg=T.WINDOW_BG)
        left.pack(side="left", fill="y", anchor="n")
        tk.Label(mapping, image=T.image("controller/controller.png", 300), bg=T.WINDOW_BG).pack(side="left", padx=16)
        right = tk.Frame(mapping, bg=T.WINDOW_BG)
        right.pack(side="left", fill="y", anchor="n")
        for parent, rows in ((left, _LEFT), (right, _RIGHT)):
            for button, key in rows:
                r = tk.Frame(parent, bg=T.WINDOW_BG)
                r.pack(anchor="w", pady=3)
                tk.Label(r, text=button, bg=T.DARK, fg="white", font=T.font(8, "bold"), padx=6).pack(side="left")
                W.label(r, tr(C + key), size=9).pack(side="left", padx=6)
        extra = tk.Frame(body, bg=T.WINDOW_BG)
        extra.pack(anchor="w")
        for key in ("Label_Bet_Buttons_From_Left_To_Down", "Label_Custom_Betsizes_From_5_To_8",
                    "Label_Custom_Betsizes_From_9_To_12", "Label_Custom_Betsizes_From_13_To_16"):
            W.label(extra, "• " + tr(C + key), muted=True, size=9).pack(anchor="w")
        link = tk.Label(body, text=own("Modifier les correspondances → Raccourcis Clavier › Tous les raccourcis",
                                       "Edit the mapping → Hotkeys › All hotkeys"), bg=T.WINDOW_BG, fg=T.ACCENT,
                        font=T.font(9, "bold"), cursor="hand2")
        link.pack(anchor="w", pady=6)
        link.bind("<Button-1>", lambda e: self._go_mapping())

    def _go_mapping(self):
        self.app.show_page("hotkeys")
        self.app.pages["hotkeys"].tabbar.select(2)

    def refresh(self):
        connected = self.app.gamepad is not None
        self.state_img.configure(image=T.image("controller/controller_connected.png" if connected
                                               else "controller/controller_mini.png", 110))
        self.state_lbl.configure(text=tr(C + "Label_Controller_Linked") if connected else "—",
                                 fg=T.GREEN[500] if connected else T.TEXT_MUTED)
        self.btn.set_text(tr(C + ("Button_Disconnet_Controller" if connected else "Button_Detect_Controller")))
        self.btn.kind = "danger" if connected else "primary"
        self.btn._draw()

    def _toggle(self):
        c = self.cfg.controller
        if self.app.gamepad:
            self.app.stop_gamepad()
            c.enabled = False
        else:
            self.state_lbl.configure(text=tr(C + "Label_Connecting"))
            self.update_idletasks()
            if self.app.start_gamepad():
                c.enabled = True
                if self.cfg.hotkey_settings.target != "focused":
                    W.info(self, tr("APP_HAMBURGER_MENU_ITEM_Title_Controller"),
                           tr("CONTROLLER_PAGE_TOASTER_HOTKEYS_MODE_UNDER_MOUSE_NL"))
            else:
                W.info(self, tr("APP_HAMBURGER_MENU_ITEM_Title_Controller"),
                       own("Aucune manette détectée (XInput sous Windows ; ailleurs : pip install pygame).",
                           "No controller found (XInput on Windows; elsewhere: pip install pygame)."))
        self.app.changed()
        self.refresh()
