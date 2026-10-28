"""Aide (guide, calculatrice poker, diagnostic) et Journal des Modifications."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from ... import APP_NAME, REPO_URL, __version__, pokermath
from ...config import config_dir
from .. import theme as T
from .. import widgets as W
from . import Page, bold, own, tr


class HelpPage(Page):
    title_key = "APP_HAMBURGER_MENU_ITEM_Title_Help"

    def build(self):
        self.header(tr(self.title_key))
        self.tabbar = self.tabs(self, [own("Guide", "Guide"), own("Calculatrice poker", "Poker calculator"),
                                       own("Diagnostic", "Diagnostics")],
                                [self._tab_guide, self._tab_calc, self._tab_diag])
        self.tabbar.select(0)

    def show_diagnostics(self):
        self.tabbar.select(2)

    # ------------------------------------------------------------------ guide
    def _tab_guide(self, f):
        hero = tk.Frame(f, bg=T.DARK, padx=20, pady=16)
        hero.pack(fill="x", padx=(0, 12), pady=(4, 10))
        tk.Label(hero, image=T.image("help/features.png", (300, 175)), bg=T.DARK).pack(side="left")
        txt = tk.Frame(hero, bg=T.DARK)
        txt.pack(side="left", padx=20, fill="both", expand=True)
        tk.Label(txt, text=tr("HELP_NL_Label_We_Love_Poker"), bg=T.DARK, fg="white", font=T.font(16, "bold"),
                 anchor="w").pack(anchor="w")
        tk.Label(txt, text=W.strip_html(tr("HELP_NL_Label_Our_Goal_Is_To_Boost_The_Online_Poker_Experience_In_All_Its_Forms")),
                 bg=T.DARK, fg=T.PRIMARY[200], font=T.font(10), wraplength=420, justify="left").pack(anchor="w", pady=6)
        tk.Label(txt, text=f"{APP_NAME} {__version__} — " + own("libre, hors ligne, sans compte ni télémétrie.",
                                                              "free, offline, no account, no telemetry."),
                 bg=T.DARK, fg="white", font=T.font(9, "bold")).pack(anchor="w")
        cards = tk.Frame(f, bg=T.WINDOW_BG)
        cards.pack(fill="x", padx=(0, 12))
        for img, title, sub, url in (
                ("help/got_questions.png", own("Guide d'utilisation", "User guide"),
                 own("README : installation, salles, layouts, raccourcis.", "README: setup, rooms, layouts, hotkeys."),
                 REPO_URL + "#readme"),
                ("help/view_body.png", own("Correspondance des fonctions", "Feature mapping"),
                 own("Ce qui est repris de l'original, remplacé ou non porté.", "What is ported, replaced or not."),
                 REPO_URL + "/blob/main/docs/ANALYSE.md"),
                ("help/ai_bot.png", tr("APP_WINDOW_STATUS_BAR_NL_Button_Report_Issue"),
                 own("Signalez un bug ou proposez une amélioration.", "Report a bug or suggest an improvement."),
                 REPO_URL + "/issues")):
            card = W.Card(cards)
            card.pack(side="left", fill="both", expand=True, padx=(0, 10))
            tk.Label(card, image=T.image(img, (220, 110)), bg=T.WINDOW_BG).pack()
            bold(card, title, size=11).pack(anchor="w", pady=(6, 0))
            W.label(card, sub, muted=True, size=9, wrap=240).pack(anchor="w")
            W.RoundButton(card, own("Ouvrir", "Open"), lambda u=url: webbrowser.open(u), kind="secondary", height=30,
                          font_size=9).pack(anchor="w", pady=(8, 0))
        W.section(f, own("Démarrage rapide", "Quick start")).pack(anchor="w", pady=(14, 4))
        for line in own(
                ["1. Configuration des Sites : vérifiez que votre salle est activée (tuile), calibrez les clics et la "
                 "sonde « action requise » si besoin.",
                 "2. Configuration des Tables : activez un layout ou créez-en un (préréglage d'origine, automatique, "
                 "manuel ou clone).",
                 "3. Raccourcis Clavier : réglez Fold / Call / Raise et les 16 boutons de mise.",
                 "4. Ouvrez vos tables : Fukuroku les place, les déplace en slot Action Requise / In Hand et "
                 "sonne quand c'est votre tour."],
                ["1. Site configuration: make sure your room is enabled, calibrate clicks and the “action required” "
                 "probe if needed.",
                 "2. Table configuration: activate a layout or create one (original preset, automatic, manual or clone).",
                 "3. Hotkeys: set Fold / Call / Raise and the 16 bet buttons.",
                 "4. Open your tables: Fukuroku places them, moves them to Action Required / In Hand slots and "
                 "rings when it is your turn."]):
            W.label(f, line, wrap=820).pack(anchor="w", pady=1)

    # ------------------------------------------------------------------ calculatrice
    def _tab_calc(self, f):
        self.calc = {k: tk.StringVar(value=v) for k, v in (("pot", "100"), ("call", "50"), ("stack", "400"),
                                                           ("bet", "75"), ("outs", "9"), ("bb", "2"))}
        self._vars.extend(self.calc.values())
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack(anchor="w", pady=(4, 8))
        labels = {"pot": own("Pot (avant la mise à suivre)", "Pot (before the call)"), "call": own("À suivre", "To call"),
                  "stack": own("Stack effectif", "Effective stack"), "bet": own("Mise (bluff / MDF)", "Bet (bluff / MDF)"),
                  "outs": "Outs", "bb": own("Grosse blinde", "Big blind")}
        for i, (k, text) in enumerate(labels.items()):
            W.label(grid, text, bold=True).grid(row=i // 3, column=(i % 3) * 2, sticky="w", padx=(0, 6), pady=3)
            ttk.Entry(grid, textvariable=self.calc[k], width=10).grid(row=i // 3, column=(i % 3) * 2 + 1, padx=(0, 20))
            self.calc[k].trace_add("write", lambda *_: self._compute())
        self.out = tk.Frame(f, bg=T.WINDOW_BG)
        self.out.pack(anchor="w", fill="x")
        self._compute()

    def _compute(self):
        for w in self.out.winfo_children():
            w.destroy()
        try:
            v = {k: float(s.get().replace(",", ".") or 0) for k, s in self.calc.items()}
        except ValueError:
            return
        pot, call, stack, bet, outs, bb = (v[k] for k in ("pot", "call", "stack", "bet", "outs", "bb"))
        rows = []
        if call > 0:
            rows.append((own("Cote du pot", "Pot odds"), f"{pokermath.pot_odds(pot, call) * 100:.1f} %  "
                                                         f"({pokermath.pot_odds_ratio(pot, call):.2f} : 1)"))
        if pot > 0:
            rows.append(("SPR", f"{pokermath.spr(stack, pot):.2f}"))
        if bet > 0 and pot > 0:
            rows.append(("MDF", f"{pokermath.mdf(pot, bet) * 100:.1f} %"))
            rows.append((own("Bluff rentable si fold ≥", "Bluff break-even fold ≥"),
                         f"{pokermath.bluff_break_even(pot, bet) * 100:.1f} %"))
        if outs > 0:
            rows.append((own("Équité (turn + river)", "Equity (turn + river)"),
                         f"{pokermath.outs_equity(int(outs), 2) * 100:.1f} %   ({own('règle 4', 'rule of 4')} "
                         f"{pokermath.outs_rule_of_2_and_4(int(outs), 2) * 100:.0f} %)"))
            rows.append((own("Équité (une carte)", "Equity (one card)"),
                         f"{pokermath.outs_equity(int(outs), 1) * 100:.1f} %"))
        if bb > 0:
            rows.append((own("Pot / stack en BB", "Pot / stack in BB"),
                         f"{pokermath.format_bb(pot, bb)} / {pokermath.format_bb(stack, bb)}"))
        for title, value in rows:
            r = tk.Frame(self.out, bg=T.PRIMARY[50], padx=12, pady=6)
            r.pack(fill="x", pady=2, padx=(0, 12))
            bold(r, title, bg=T.PRIMARY[50], fg=T.PRIMARY[800]).pack(side="left")
            tk.Label(r, text=value, bg=T.PRIMARY[50], fg=T.TEXT, font=T.digital(16)).pack(side="right")

    # ------------------------------------------------------------------ diagnostic
    def _tab_diag(self, f):
        b = self.app.backend
        info = [f"{APP_NAME} {__version__}", f"Backend : {b.name}", f"Configuration : {config_dir()}",
                f"Écrans : {', '.join(f'{s.w}×{s.h}+{s.x}+{s.y}' for s in self.app.manager.screens)}"]
        info += [f"! {m}" for m in b.diagnostics()]
        if self.app.input.error:
            info.append(f"! {self.app.input.error}")
        for line in info:
            W.label(f, line, size=9, muted=line.startswith("!") is False).pack(anchor="w")
        W.section(f, own("Notifications", "Notifications")).pack(anchor="w", pady=(10, 4))
        self.log = tk.Text(f, height=14, bg=T.GRAY[50], fg=T.TEXT, font=("Courier", 9), bd=0, highlightthickness=1,
                           highlightbackground=T.BORDER)
        self.log.pack(fill="both", expand=True, padx=(0, 12))
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(anchor="w", pady=6)
        W.RoundButton(row, own("Rafraîchir", "Refresh"), self._fill_log, kind="secondary", height=30,
                      font_size=9).pack(side="left")
        W.RoundButton(row, own("Fenêtres détectées", "Detected windows"), self._windows, kind="ghost", height=30,
                      font_size=9).pack(side="left", padx=6)
        self._fill_log()

    def _fill_log(self):
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(reversed(self.app.notifications)))

    def _windows(self):
        m = self.app.manager
        lines = []
        for w in self.app.backend.list_windows():
            found = m.classify(w)
            tag = f"[{found[0].name} · {found[1]}]" if found else "[—]"
            lines.append(f"{tag:34} {w.process_name:20} {w.title}")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(lines))

    def refresh(self):
        if hasattr(self, "log"):
            self._fill_log()


CHANGES = {
    "2.0.0": {
        "new": ["Interface au style de l'original : menu latéral violet, pages et onglets d'origine, textes en 10 langues.",
                "Sons, images, polices et layouts prédéfinis d'origine.",
                "Slots Action Requise, Queue, In Hand, Replay et Lobby ; un seul type dynamique par layout.",
                "Création de layout : manuelle, automatique, préréglage d'origine, clonage ; éditeur de slots.",
                "Changement automatique de layout selon le nombre de tables ; raccourci par layout.",
                "16 boutons de mise (BB / % pot / multiplicateur / géométrique) et modes de relance.",
                "Contournement des hotkeys par salle, bordures de table, alarme différée, compteurs AR / ST / mains, "
                "overlay de boutons de mise, capture d'écran, historique des sessions."],
        "changes": ["Configuration v2 (migration automatique de la 1.0).", "Export / import des paramètres en .zip."],
        "fixes": ["Bouton de mise sans montant calculable : repli sur le raccourci du client ou le clic."],
    },
    "1.0.0": {"new": ["Première version : placement par slots, flux action requise, raccourcis, RNG, minuteur."],
              "changes": [], "fixes": []},
}


class ChangelogPage(Page):
    title_key = "CHANGELOG_PAGE_NL_Title_Whats_New"

    def build(self):
        self.header(tr(self.title_key))
        sf = W.ScrollFrame(self)
        sf.pack(fill="both", expand=True, padx=(28, 8))
        for version, c in CHANGES.items():
            head = tk.Frame(sf.inner, bg=T.WINDOW_BG)
            head.pack(fill="x", pady=(8, 4))
            tk.Label(head, text=f"v{version}", bg=T.ACCENT, fg="white", font=T.font(10, "bold"), padx=10,
                     pady=2).pack(side="left")
            for key, items, color in (("CHANGELOG_PAGE_NL_Label_New_Functionalities", c["new"], T.GREEN[500]),
                                      ("CHANGELOG_PAGE_NL_Label_General_Changes", c["changes"], T.BLUE[600]),
                                      ("CHANGELOG_PAGE_NL_Label_Fixed_Bugs", c["fixes"], T.ORANGE[500])):
                if not items:
                    continue
                bold(sf.inner, tr(key), fg=color).pack(anchor="w", pady=(6, 2))
                for it in items:
                    W.label(sf.inner, "•  " + it, wrap=860).pack(anchor="w", padx=(10, 0))
