"""Configuration des Tables : layouts, création (4 méthodes), éditeur de slots,
changement automatique de layout et raccourcis de slots."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...geometry import Rect
from ...hotkeys import Action, HotKey
from ...layout import DEFAULT_TABLE_ASPECT, DYNAMIC_SLOT_KINDS, SLOT_COLORS, Layout, Slot, SlotKind, presets_for
from .. import theme as T
from .. import widgets as W
from . import HotkeyField, Page, action_field, action_label, bold, combo, slot_labels, spin, tr


def _light(color: str, k: float = 0.55) -> str:
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (255 - x) * k) for x in a)


class LayoutCanvas(tk.Canvas):
    """Aperçu / éditeur : écrans en gris, slots colorés par type et numérotés."""

    def __init__(self, master, screens: list[Rect], width: int = 640, height: int = 340, editable: bool = False,
                 on_select=None, on_change=None):
        super().__init__(master, width=width, height=height, bg=T.GRAY[100], highlightthickness=0)
        self.screens, self.editable = screens, editable
        self.on_select, self.on_change = on_select, on_change
        self.layout: Layout | None = None
        self.selected: Slot | None = None
        self.faults: list[Slot] = []
        self.lock_aspect = False
        self._drag = None
        self.bind("<Configure>", lambda e: self.draw())
        if editable:
            self.bind("<ButtonPress-1>", self._press)
            self.bind("<B1-Motion>", self._motion)
            self.bind("<ButtonRelease-1>", self._release)

    # ------------------------------------------------------------------ transformation
    def _bounds(self) -> Rect:
        rects = list(self.screens) + ([s.rect for s in self.layout.slots] if self.layout else [])
        x, y = min(r.x for r in rects), min(r.y for r in rects)
        return Rect(x, y, max(r.right for r in rects) - x, max(r.bottom for r in rects) - y)

    def _transform(self):
        b = self._bounds()
        w, h = max(50, self.winfo_width()), max(50, self.winfo_height())
        k = min((w - 20) / max(1, b.w), (h - 20) / max(1, b.h))
        ox = (w - b.w * k) / 2 - b.x * k
        oy = (h - b.h * k) / 2 - b.y * k
        return k, ox, oy

    def to_canvas(self, r: Rect):
        k, ox, oy = self._transform()
        return r.x * k + ox, r.y * k + oy, r.right * k + ox, r.bottom * k + oy

    # ------------------------------------------------------------------ dessin
    def show(self, layout: Layout | None, faults: list[Slot] | None = None):
        self.layout = layout
        self.faults = faults or []
        self.draw()

    def draw(self):
        self.delete("all")
        if not self.screens:
            return
        for i, s in enumerate(self.screens, start=1):
            x1, y1, x2, y2 = self.to_canvas(s)
            self.create_rectangle(x1, y1, x2, y2, fill=T.GRAY[800], outline=T.GRAY[600])
            self.create_text(x2 - 6, y2 - 6, text=f"🖵 {i}  {s.w}×{s.h}", anchor="se", fill=T.GRAY[400],
                             font=T.font(8))
        if not self.layout:
            return
        labels = slot_labels()
        for slot in self.layout.slots:
            color = SLOT_COLORS[slot.kind]
            x1, y1, x2, y2 = self.to_canvas(slot.rect)
            bad = slot in self.faults
            sel = slot is self.selected
            self.create_rectangle(x1, y1, x2, y2, fill=_light(color, 0.35), outline=T.RED[500] if bad else
                                  ("white" if sel else color), width=3 if (bad or sel) else 1)
            text = f"{labels[slot.kind]}\n{self.layout.number_of(slot)}"
            if slot.stacks:
                text += "  ⧉"
            if slot.kind == SlotKind.LOBBY and slot.site:
                text += f"\n{slot.site}"
            size = 9 if (x2 - x1) > 90 else 7
            self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text, fill="white", font=T.font(size, "bold"),
                             justify="center")
            if self.editable and sel:
                self.create_rectangle(x2 - 8, y2 - 8, x2, y2, fill="white", outline=color)

    # ------------------------------------------------------------------ édition à la souris
    def _slot_at(self, x, y):
        for slot in reversed(self.layout.slots if self.layout else []):
            x1, y1, x2, y2 = self.to_canvas(slot.rect)
            if x1 <= x <= x2 and y1 <= y <= y2:
                return slot, (x >= x2 - 10 and y >= y2 - 10)
        return None, False

    def _press(self, e):
        slot, corner = self._slot_at(e.x, e.y)
        self.selected = slot
        if slot:
            self._drag = (e.x, e.y, Rect(slot.rect.x, slot.rect.y, slot.rect.w, slot.rect.h), corner)
        if self.on_select:
            self.on_select(slot)
        self.draw()

    def _motion(self, e):
        if not self._drag or not self.selected:
            return
        x0, y0, r, corner = self._drag
        k = self._transform()[0]
        dx, dy = round((e.x - x0) / k), round((e.y - y0) / k)
        if corner:
            w = max(80, r.w + dx)
            h = max(60, r.h + dy)
            if self.lock_aspect and r.h:
                h = round(w * r.h / r.w)
            self.selected.rect = Rect(r.x, r.y, w, h)
        else:
            self.selected.rect = Rect(r.x + dx, r.y + dy, r.w, r.h)
        self.draw()

    def _release(self, e):
        if self._drag and self.on_change:
            self.on_change()
        self._drag = None


class LayoutsPage(Page):
    title_key = "APP_HAMBURGER_MENU_ITEM_Title_Layout"

    def build(self):
        self.main = tk.Frame(self, bg=T.WINDOW_BG)
        self.main.pack(fill="both", expand=True)
        self.editor: LayoutEditor | None = None
        bar = tk.Frame(self.main, bg=T.WINDOW_BG)
        bar.pack(fill="x", padx=28, pady=(20, 8))
        W.page_title(bar, tr(self.title_key)).pack(side="left")
        self.tabbar = self.tabs(self.main, [tr("LAYOUT_CONFIGURATION_NL_Tab_Header_Configuration"),
                                            tr("LAYOUT_CONFIGURATION_NL_Tab_Header_Automatic_Layout_Switch"),
                                            tr("LAYOUT_CONFIGURATION_NL_Tab_Header_Layout_Hotkeys")],
                                [self._tab_config, self._tab_auto, self._tab_hotkeys])
        self.tabbar.select(0)

    @property
    def screens(self) -> list[Rect]:
        return self.app.manager.refresh_screens() or [Rect(0, 0, 1920, 1080)]

    # ================================================================== onglet Configuration
    def _tab_config(self, f):
        top = tk.Frame(f, bg=T.WINDOW_BG)
        top.pack(fill="x", pady=(4, 8))
        bold(top, tr("LAYOUT_CONFIGURATION_NL_Label_Active_Layout"), size=11, fg=T.PRIMARY[700]).pack(side="left")
        self.active_lbl = bold(top, "", size=11)
        self.active_lbl.pack(side="left", padx=6)
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack(fill="both", expand=True)
        left = tk.Frame(row, bg=T.WINDOW_BG)
        left.pack(side="left", fill="y", padx=(0, 16))
        bold(left, tr("LAYOUT_CONFIGURATION_NL_Label_Select_Layout")).pack(anchor="w")
        self.listbox = tk.Listbox(left, height=12, width=28, activestyle="none", font=T.font(10), bd=0,
                                  highlightthickness=1, highlightbackground=T.BORDER, selectbackground=T.PRIMARY[100],
                                  selectforeground=T.PRIMARY[900])
        self.listbox.pack(anchor="w", pady=(4, 12), fill="y")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._preview())
        self.listbox.bind("<Double-Button-1>", lambda e: self._activate())
        bold(left, tr("LAYOUT_CONFIGURATION_NL_Layout_Layout_Actions")).pack(anchor="w", pady=(0, 4))
        for key, cmd, kind in (("LAYOUT_CONFIGURATION_NL_Button_Activate_Layout", self._activate, "primary"),
                               ("LAYOUT_CONFIGURATION_NL_Button_Edit_Layout", self._edit, "secondary"),
                               ("LAYOUT_CONFIGURATION_NL_Button_Delete_Layout", self._delete, "danger"),
                               ("LAYOUT_CONFIGURATION_NL_Button_Create_New_Layout", self._create, "dark")):
            W.RoundButton(left, tr(key), cmd, kind=kind, width=230, height=34, font_size=9).pack(anchor="w", pady=3)
        right = tk.Frame(row, bg=T.WINDOW_BG)
        right.pack(side="left", fill="both", expand=True)
        bold(right, tr("LAYOUT_CONFIGURATION_NL_Label_Layout_Preview")).pack(anchor="w")
        self.preview = LayoutCanvas(right, self.screens, 620, 330)
        self.preview.pack(fill="both", expand=True, pady=(4, 6))
        legend = tk.Frame(right, bg=T.WINDOW_BG)
        legend.pack(anchor="w")
        for kind, text in slot_labels().items():
            tk.Label(legend, text="■", fg=SLOT_COLORS[kind], bg=T.WINDOW_BG, font=T.font(11)).pack(side="left")
            tk.Label(legend, text=text, bg=T.WINDOW_BG, fg=T.TEXT_MUTED, font=T.font(8)).pack(side="left", padx=(0, 10))
        self.desc = tk.Label(right, text="", bg=T.WINDOW_BG, fg=T.TEXT_MUTED, font=T.font(9), anchor="w")
        self.desc.pack(anchor="w")

    def refresh(self):
        if not hasattr(self, "listbox"):
            return
        names = [l.name for l in self.cfg.layouts]
        sel = self._selected_name() or self.cfg.active_layout
        self.listbox.delete(0, "end")
        for n in names:
            self.listbox.insert("end", ("● " if n == self.cfg.active_layout else "   ") + n)
        if sel in names:
            self.listbox.selection_set(names.index(sel))
            self.listbox.see(names.index(sel))
        self.active_lbl.configure(text=self.cfg.active_layout)
        self.preview.screens = self.screens
        self._preview()

    def refresh_live(self):
        if hasattr(self, "active_lbl") and self.active_lbl.cget("text") != self.cfg.active_layout:
            self.refresh()

    def _selected_name(self) -> str | None:
        if not hasattr(self, "listbox"):
            return None
        sel = self.listbox.curselection()
        return self.cfg.layouts[sel[0]].name if sel and sel[0] < len(self.cfg.layouts) else None

    def _selected(self) -> Layout | None:
        name = self._selected_name()
        return next((l for l in self.cfg.layouts if l.name == name), None)

    def _preview(self):
        layout = self._selected()
        self.preview.show(layout, layout.faults(self.preview.screens) if layout else [])
        if layout:
            counts = {}
            for s in layout.slots:
                counts[s.kind] = counts.get(s.kind, 0) + 1
            labels = slot_labels()
            self.desc.configure(text="   ".join(f"{labels[k]} × {n}" for k, n in counts.items()) +
                                (f"   —   {layout.description}" if layout.description else ""))

    def _activate(self):
        layout = self._selected()
        if layout is None:
            return
        if self.cfg.auto_switch.enabled:
            if not W.ask_yes_no(self, tr("LAYOUT_CONFIGURATION_NL_ON_TABLES_LAYOUT_CONFIGURATION_Auto_Swap_Caption"),
                                tr("LAYOUT_CONFIGURATION_NL_ON_TABLES_LAYOUT_CONFIGURATION_Auto_Swap_Message"),
                                tr("LAYOUT_CONFIGURATION_NL_Button_Activate_Layout"), tr("RNG_SETTINGS_Button_Cancel")):
                return
            self.cfg.auto_switch.enabled = False
        self.app.manager.submit(self.app.manager.switch_layout, layout.name)
        self.cfg.active_layout = layout.name
        self.app.changed()
        self.refresh()

    def _delete(self):
        layout = self._selected()
        if layout is None or len(self.cfg.layouts) <= 1:
            return
        if not W.ask_yes_no(self, tr("DIALOG_DELETE_LAYOUT_NL_Title_Delete_Layout"),
                            f"{tr('DIALOG_DELETE_LAYOUT_NL_Body_Are_You_Sure_Deleteting')}{layout.name} ?",
                            tr("DIALOG_DELETE_LAYOUT_NL_Button_Delete"), tr("DIALOG_DELETE_LAYOUT_NL_Button_Cancel"),
                            image="layout/delete.png", danger=True):
            return
        self.cfg.layouts.remove(layout)
        if self.cfg.active_layout == layout.name:
            self.cfg.active_layout = self.cfg.layouts[0].name
            self.app.manager.submit(self.app.manager.switch_layout, self.cfg.active_layout)
        self.app.changed()
        self.refresh()

    def _new_name(self) -> str:
        names = {l.name for l in self.cfg.layouts}
        i = len(names) + 1
        while f"Layout {i}" in names:
            i += 1
        return f"Layout {i}"

    def _create(self):
        CreateLayoutDialog(self)

    def _edit(self, layout: Layout | None = None, is_new: bool = False):
        layout = layout or self._selected()
        if layout is None:
            return
        self.main.pack_forget()
        self.editor = LayoutEditor(self, layout, is_new)
        self.editor.pack(fill="both", expand=True)

    def close_editor(self, saved: Layout | None = None, original_name: str | None = None):
        if self.editor:
            self.editor.destroy()
            self.editor = None
        if saved is not None:
            existing = next((l for l in self.cfg.layouts if l.name == original_name), None)
            if existing is not None:
                self.cfg.layouts[self.cfg.layouts.index(existing)] = saved
            else:
                self.cfg.layouts.append(saved)
            if self.cfg.active_layout in (original_name, saved.name):
                self.cfg.active_layout = saved.name
                self.app.manager.submit(self.app.manager.switch_layout, saved.name)
            self.app.save()
        self.main.pack(fill="both", expand=True)
        self.refresh()
        if saved is not None:
            names = [l.name for l in self.cfg.layouts]
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(names.index(saved.name))
            self._preview()

    # ================================================================== onglet Changement Auto Layout
    def _tab_auto(self, f):
        a = self.cfg.auto_switch
        W.banner(f, W.strip_html(tr("LAYOUT_CONFIGURATION_NL_Info_Automatically_Switch_From_An_Initial_Layout"))
                 ).pack(fill="x", pady=(4, 10), padx=(0, 12))
        en = self.var(a, "enabled")
        head = tk.Frame(f, bg=T.WINDOW_BG)
        head.pack(fill="x")
        W.ToggleSwitch(head, en).pack(side="left")
        state = bold(head, "", size=11)
        state.pack(side="left", padx=10)
        upd = lambda *_: state.configure(text=tr("LAYOUT_CONFIGURATION_NL_Switch_Feature_Enabled") if en.get()
                                         else tr("LAYOUT_CONFIGURATION_NL_Switch_Feature_Disabled"),
                                         fg=T.GREEN[500] if en.get() else T.TEXT_MUTED)
        en.trace_add("write", upd)
        upd()
        W.section(f, tr("LAYOUT_CONFIGURATION_NL_Label_Auto_Switch_Options")).pack(anchor="w", pady=(14, 6))
        names = [l.name for l in self.cfg.layouts]
        ini = tk.Frame(f, bg=T.WINDOW_BG)
        ini.pack(anchor="w")
        bold(ini, tr("LAYOUT_CONFIGURATION_NL_Label_Initial_Layout")).pack(side="left", padx=(0, 8))
        combo(ini, self.var(a, "initial_layout", str), names, 24).pack(side="left")
        self.rules_box = tk.Frame(f, bg=T.WINDOW_BG)
        self.rules_box.pack(anchor="w", pady=8, fill="x")
        self._draw_rules()
        W.RoundButton(f, "+  " + tr("SWITCH_LAYOUT_Label_Choose").capitalize(), self._add_rule, kind="secondary",
                      height=30, font_size=9).pack(anchor="w")
        self.separator(f)
        self.row(f, "layout/go_back.png", "LAYOUT_CONFIGURATION_NL_Label_Go_Back_To_Previous_Layout_If_Table_Decrease",
                 a, "go_back_on_decrease")
        self.row(f, "layout/ask_before.png", "LAYOUT_CONFIGURATION_NL_Label_Ask_Before_Switching_Layout_Automatically",
                 a, "ask_before")
        W.RoundButton(f, tr("LAYOUT_CONFIGURATION_NL_Button_Save_Changes"), self.app.save).pack(anchor="e", pady=10,
                                                                                               padx=12)

    def _draw_rules(self):
        for w in self.rules_box.winfo_children():
            w.destroy()
        names = [l.name for l in self.cfg.layouts]
        rules = self.cfg.auto_switch.rules
        for i, rule in enumerate(rules):
            r = tk.Frame(self.rules_box, bg=T.PRIMARY[50], padx=10, pady=6)
            r.pack(anchor="w", pady=2, fill="x", padx=(0, 12))
            bold(r, tr("SWITCH_LAYOUT_Label_If_There_Are"), bg=T.PRIMARY[50], fg=T.PRIMARY[800]).pack(side="left")
            n = self.keep(tk.IntVar(value=int(rule[0])))
            spin(r, n, 1, 99, width=4).pack(side="left", padx=6)
            bold(r, tr("SWITCH_LAYOUT_Open_Tables"), bg=T.PRIMARY[50], fg=T.PRIMARY[800]).pack(side="left")
            bold(r, "  →  " + tr("SWITCH_LAYOUT_Activate_The_Layout"), bg=T.PRIMARY[50],
                 fg=T.PRIMARY[800]).pack(side="left")
            name = self.keep(tk.StringVar(value=rule[1]))
            combo(r, name, names, 20).pack(side="left", padx=6)

            def write(*_, i=i, n=n, name=name):
                try:
                    rules[i] = [int(n.get()), name.get()]
                    self.app.changed()
                except (tk.TclError, ValueError, IndexError):
                    pass
            n.trace_add("write", write)
            name.trace_add("write", write)
            x = tk.Label(r, text="✕", bg=T.PRIMARY[50], fg=T.RED[500], font=T.font(11, "bold"), cursor="hand2")
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, i=i: self._del_rule(i))

    def _add_rule(self):
        rules = self.cfg.auto_switch.rules
        n = max((int(r[0]) for r in rules), default=0) + 2
        rules.append([n, self.cfg.layouts[-1].name if self.cfg.layouts else ""])
        self.app.changed()
        self._draw_rules()

    def _del_rule(self, i: int):
        del self.cfg.auto_switch.rules[i]
        self.app.changed()
        self._draw_rules()

    # ================================================================== onglet Raccourcis Layout
    def _tab_hotkeys(self, f):
        W.banner(f, tr("SETTINGS_NL_Info_Hotkeys_Will_Only_Work_Once_You_Leave_This_View")).pack(fill="x", pady=(4, 10),
                                                                                                padx=(0, 12))
        cols = tk.Frame(f, bg=T.WINDOW_BG)
        cols.pack(fill="x")
        for col_i, (icon, title, sub, prefix) in enumerate((
                ("layout/hotkeys/playing_slot.png", "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Playing_Slot",
                 "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Send_Table_To_Playing_Slot", "SendTableToPlayingSlot"),
                ("layout/hotkeys/observer_slot.png", "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Observer_Slot",
                 "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Send_Table_To_Observer_Slot", "SendTableToObserverSlot"))):
            card = W.Card(cols)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12))
            head = tk.Frame(card, bg=T.WINDOW_BG)
            head.pack(fill="x")
            tk.Label(head, image=T.image(icon, 44), bg=T.WINDOW_BG).pack(side="left")
            txt = tk.Frame(head, bg=T.WINDOW_BG)
            txt.pack(side="left", padx=8)
            bold(txt, tr(title), size=11).pack(anchor="w")
            W.label(txt, tr(sub), muted=True, size=9).pack(anchor="w")
            no = tr("LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Playing_Slot_No" if col_i == 0
                    else "LAYOUT_CONFIGURATION_NL_Hotkeys_Label_Observer_Slot_No")
            for i in range(1, 6):
                r = tk.Frame(card, bg=T.WINDOW_BG)
                r.pack(fill="x", pady=2)
                W.label(r, f"{no}{i}").pack(side="left")
                action_field(r, self.app, Action(f"{prefix}{i}")).pack(side="right")
        card = W.Card(f)
        card.pack(fill="x", pady=12, padx=(0, 12))
        for icon, action, sub in (
                ("layout/hotkeys/lock_table.png", Action.LockTableFromDynamicFlow,
                 "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Lock_Table_Of_Dynamic_Flow"),
                ("layout/hotkeys/move_table_next.png", Action.MoveTableToNextSlot,
                 "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Move_Table_To_Next_Slot"),
                ("layout/hotkeys/move_table_previous.png", Action.MoveTableToPreviousSlot,
                 "LAYOUT_CONFIGURATION_NL_HOTKEYS_Label_Move_Table_To_Previous_Slot"),
                ("layout/swap.png", Action.MoveTableToNextSlotWithSwapping, None),
                ("layout/swap.png", Action.MoveTableToPreviousSlotWithSwapping, None)):
            W.SettingRow(card, icon, action_label(action), subtitle=tr(sub) if sub else "",
                         control=lambda m, a=action: action_field(m, self.app, a)).pack(fill="x")


# ====================================================================== création
class CreateLayoutDialog(W.AppDialog):
    """« Créer un Nouveau Layout » : manuellement, automatiquement, préréglage, clonage."""

    def __init__(self, page: LayoutsPage):
        self.page = page
        super().__init__(page, tr("CREATE_NEW_LAYOUT_NL_Title_Create_New_Layout"), body=self._body,
                         buttons=[(tr("RNG_SETTINGS_Button_Cancel"), "ghost", None)], width=640)

    def _body(self, f):
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack()
        has_presets = any(presets_for(s) for s in self.page.screens)
        options = (("layout/drag.png", "CREATE_NEW_LAYOUT_NL_Button_Create_Manually", self._manual, True),
                   ("layout/size.png", "CREATE_NEW_LAYOUT_NL_Button_Create_Automatically", self._auto, True),
                   ("layout/treasure.png", "CREATE_NEW_LAYOUT_NL_Button_Start_Form_Preset_Layout", self._preset,
                    has_presets),
                   ("layout/swap.png", "CREATE_NEW_LAYOUT_NL_Button_Clone_Existing_Layout", self._clone, True))
        for i, (icon, key, cmd, enabled) in enumerate(options):
            card = tk.Frame(grid, bg=T.PRIMARY[50] if enabled else T.GRAY[100], padx=14, pady=12,
                            cursor="hand2" if enabled else "arrow", highlightthickness=2,
                            highlightbackground=T.PRIMARY[50] if enabled else T.GRAY[100])
            card.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="nsew")
            img = tk.Label(card, image=T.image(icon, 70), bg=card.cget("bg"))
            img.pack()
            txt = tk.Label(card, text=tr(key), bg=card.cget("bg"), fg=T.PRIMARY[800] if enabled else T.GRAY[500],
                           font=T.font(10, "bold"), wraplength=230, width=26)
            txt.pack(pady=(6, 0))
            if enabled:
                for w in (card, img, txt):
                    w.bind("<Button-1>", lambda e, c=cmd: self._go(c))
                    w.bind("<Enter>", lambda e, c=card: c.configure(highlightbackground=T.ACCENT))
                    w.bind("<Leave>", lambda e, c=card: c.configure(highlightbackground=T.PRIMARY[50]))
            else:
                W.Tooltip(card, tr("CREATE_NEW_LAYOUT_NL_Help_Option_Unavaliable_For_Your_Screen_Resolution"))

    def _go(self, cmd):
        self.close(None)
        cmd()

    def _manual(self):
        p = self.page
        p._edit(Layout(p._new_name(), [], DEFAULT_TABLE_ASPECT), is_new=True)

    def _auto(self):
        AutoLayoutDialog(self.page)

    def _preset(self):
        PresetDialog(self.page)

    def _clone(self):
        CloneDialog(self.page)


class AutoLayoutDialog(W.AppDialog):
    """Création automatique : taille de slot et marge, puis répartition jeu/observation/replay."""

    def __init__(self, page: LayoutsPage):
        self.page = page
        screen = page.screens[0]
        self.v = {k: tk.IntVar(value=v) for k, v in (("w", screen.w // 3), ("h", round(screen.w / 3 / DEFAULT_TABLE_ASPECT)),
                                                      ("pad", 0), ("playing", 0), ("observer", 0), ("replay", 0),
                                                      ("screen", 1))}
        super().__init__(page, tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Title_Create_New_Layout_Automatically"),
                         body=self._body, buttons=[(tr("RNG_SETTINGS_Button_Cancel"), "ghost", None),
                                                   (tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Button_Done"), "primary",
                                                    True)], width=560)

    def _body(self, f):
        W.label(f, tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Label_Select_Size_Of_Slot_You_Want"), muted=True,
                wrap=520).pack(anchor="w")
        grid = tk.Frame(f, bg=T.WINDOW_BG)
        grid.pack(anchor="w", pady=8)
        rows = [("screen", "🖵", 1, len(self.page.screens), 1),
                ("w", tr("SLOT_SIZE_SELECTION_WINDOW_Label_Width"), 200, 4000, 10),
                ("h", tr("SLOT_SIZE_SELECTION_WINDOW_Label_Height"), 150, 3000, 10),
                ("pad", tr("SLOT_SIZE_SELECTION_WINDOW_Label_Slot_Padding").capitalize(), 0, 200, 2),
                ("playing", tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Label_Playing_Slots"), 0, 60, 1),
                ("observer", tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Label_Observer_Slots"), 0, 60, 1),
                ("replay", tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Label_Replay_Slots"), 0, 10, 1)]
        for i, (k, text, lo, hi, inc) in enumerate(rows):
            W.label(grid, text, bold=True).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 10))
            spin(grid, self.v[k], lo, hi, inc, 7).grid(row=i, column=1, sticky="w")
        self.avail = W.label(f, "", bold=True)
        self.avail.pack(anchor="w")
        for v in self.v.values():
            v.trace_add("write", lambda *_: self._update())
        self._update()

    def _cells(self) -> list[Rect]:
        try:
            s = self.page.screens[max(0, min(len(self.page.screens), self.v["screen"].get()) - 1)]
            w, h, pad = self.v["w"].get(), self.v["h"].get(), self.v["pad"].get()
        except tk.TclError:
            return []
        if w <= 0 or h <= 0:
            return []
        cols = max(0, (s.w + pad) // (w + pad))
        rows = max(0, (s.h + pad) // (h + pad))
        ox = s.x + (s.w - (cols * w + (cols - 1) * pad)) // 2
        oy = s.y + (s.h - (rows * h + (rows - 1) * pad)) // 2
        return [Rect(ox + c * (w + pad), oy + r * (h + pad), w, h) for r in range(rows) for c in range(cols)]

    def _update(self):
        n = len(self._cells())
        self.avail.configure(text=f"{tr('CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Label_Avaliable_Slots')} : {n}")
        try:
            if n and self.v["playing"].get() + self.v["observer"].get() + self.v["replay"].get() == 0:
                self.v["playing"].set(n)
        except tk.TclError:
            pass

    def close(self, value):
        cells = self._cells() if value else []
        super().close(value)
        if not value or not cells:
            return
        slots, i = [], 0
        for kind, key in ((SlotKind.PLAYING, "playing"), (SlotKind.OBSERVER, "observer"), (SlotKind.REPLAY, "replay")):
            for _ in range(self.v[key].get()):
                if i >= len(cells):
                    break
                slots.append(Slot(len(slots) + 1, kind, cells[i], 0 if kind == SlotKind.OBSERVER else 1))
                i += 1
        self.page._edit(Layout(self.page._new_name(), slots, DEFAULT_TABLE_ASPECT), is_new=True)


class PresetDialog(W.AppDialog):
    def __init__(self, page: LayoutsPage):
        self.page = page
        self.items = [(si, p) for si, s in enumerate(page.screens) for p in presets_for(s)]
        super().__init__(page, tr("CREATE_NEW_LAYOUT_FROM_PRESET_NL_Title_Create_New_Layout_From_Preset"),
                         body=self._body, buttons=[(tr("RNG_SETTINGS_Button_Cancel"), "ghost", None),
                                                   (tr("CREATE_NEW_LAYOUT_FROM_EXISTING_NL_Button_Save"), "primary",
                                                    True)], width=640)

    def _body(self, f):
        row = tk.Frame(f, bg=T.WINDOW_BG)
        row.pack()
        self.lb = tk.Listbox(row, width=44, height=12, font=T.font(9), activestyle="none", bd=0, highlightthickness=1,
                             highlightbackground=T.BORDER, selectbackground=T.PRIMARY[100])
        self.lb.pack(side="left", fill="y")
        multi = len(self.page.screens) > 1
        for si, p in self.items:
            self.lb.insert("end", (f"🖵{si + 1}  " if multi else "") + p.description)
        self.canvas = LayoutCanvas(row, [], 300, 190)
        self.canvas.pack(side="left", padx=(10, 0))
        self.lb.bind("<<ListboxSelect>>", lambda e: self._show())
        if self.items:
            self.lb.selection_set(0)
            self.after(50, self._show)

    def _built(self) -> Layout | None:
        sel = self.lb.curselection()
        if not sel:
            return None
        si, p = self.items[sel[0]]
        screen = self.page.screens[si]
        layout = p.build(self.page._new_name(), screen)
        self.canvas.screens = [screen]
        return layout

    def _show(self):
        self.canvas.show(self._built())

    def close(self, value):
        layout = self._built() if value else None
        super().close(value)
        if layout:
            self.page._edit(layout, is_new=True)


class CloneDialog(W.AppDialog):
    def __init__(self, page: LayoutsPage):
        self.page = page
        self.src = tk.StringVar(value=page.cfg.active_layout)
        self.name = tk.StringVar(value=page._new_name())
        super().__init__(page, tr("CREATE_NEW_LAYOUT_FROM_EXISTING_NL_Title_Clone_Layout"), body=self._body,
                         buttons=[(tr("RNG_SETTINGS_Button_Cancel"), "ghost", None),
                                  (tr("CREATE_NEW_LAYOUT_FROM_EXISTING_NL_Button_Save"), "primary", True)])

    def _body(self, f):
        W.label(f, tr("CREATE_NEW_LAYOUT_FROM_EXISTING_NL_Label_Select_A_Layout_To_Clone"), bold=True).pack(anchor="w")
        combo(f, self.src, [l.name for l in self.page.cfg.layouts], 34).pack(anchor="w", pady=(2, 10))
        W.label(f, tr("CREATE_NEW_LAYOUT_FROM_EXISTING_NL_Label_Write_A_Name_For_The_Layout"), bold=True).pack(anchor="w")
        ttk.Entry(f, textvariable=self.name, width=36).pack(anchor="w", pady=2)

    def close(self, value):
        src, name = self.src.get(), self.name.get().strip()
        super().close(value)
        if not value or not name or any(l.name == name for l in self.page.cfg.layouts):
            return
        layout = self.page.cfg.layout(src)
        if layout:
            clone = Layout.from_dict(layout.to_dict())
            clone.name = name
            self.page.cfg.layouts.append(clone)
            self.page.app.changed()
            self.page.refresh()


# ====================================================================== éditeur
class LayoutEditor(tk.Frame):
    """« Modifier le Layout » : glisser/redimensionner les slots, ajouter, propriétés."""

    def __init__(self, page: LayoutsPage, layout: Layout, is_new: bool):
        super().__init__(page, bg=T.WINDOW_BG)
        self.page, self.app = page, page.app
        self.original_name = None if is_new else layout.name
        self.layout = Layout.from_dict(layout.to_dict())
        self.screens = page.screens
        self.vars: list[tk.Variable] = []

        bar = tk.Frame(self, bg=T.WINDOW_BG)
        bar.pack(fill="x", padx=28, pady=(20, 8))
        back = tk.Label(bar, text="‹ " + tr("APP_HAMBURGER_MENU_ITEM_Title_Back"), bg=T.WINDOW_BG, fg=T.ACCENT,
                        font=T.font(10, "bold"), cursor="hand2")
        back.pack(side="left", padx=(0, 14))
        back.bind("<Button-1>", lambda e: page.close_editor())
        W.page_title(bar, tr("EDIT_LAYOUT_NL_Title_Edit_Layout")).pack(side="left")
        W.RoundButton(bar, tr("EDIT_LAYOUT_NL_Button_Save_Changes"), self._save).pack(side="right")

        body = tk.Frame(self, bg=T.WINDOW_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        left = tk.Frame(body, bg=T.WINDOW_BG)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = LayoutCanvas(left, self.screens, 640, 380, editable=True, on_select=self._select,
                                   on_change=self._changed)
        self.canvas.pack(fill="both", expand=True)
        W.label(left, tr("CREATE_NEW_LAYOUT_AUTOMATICALLY_NL_Label_You_Can_Drag_And_From_Corner_Drop_To_Modify_Sizes"),
                muted=True, size=8).pack(anchor="w", pady=(4, 0))

        side = W.ScrollFrame(body)
        side.configure(width=330)
        side.pack(side="left", fill="y", padx=(14, 0))
        side.pack_propagate(False)
        p = side.inner
        W.label(p, tr("EDIT_LAYOUT_NL_Label_Layout_Name"), bold=True).pack(anchor="w")
        self.name_var = self._v(tk.StringVar(value=self.layout.name))
        ttk.Entry(p, textvariable=self.name_var, width=30).pack(anchor="w", pady=(2, 8))
        W.label(p, tr("EDIT_LAYOUT_NL_Label_Hotkey_To_Switch_Layout_During_Session"), bold=True, wrap=300).pack(anchor="w")
        HotkeyField(p, self.app, lambda: self.layout.switch_hotkey or None, self._set_switch_hotkey,
                    title=self.layout.name).pack(anchor="w", pady=(2, 8))
        stack = self._v(tk.BooleanVar(value=self.layout.stack_ar))
        stack.trace_add("write", lambda *_: setattr(self.layout, "stack_ar", stack.get()))
        W.SettingRow(p, "layout/stack.png", tr("EDIT_LAYOUT_NL_Label_Stack_Tables_In_Ar_Slot"), stack).pack(fill="x")
        lock = self._v(tk.BooleanVar(value=False))
        lock.trace_add("write", lambda *_: setattr(self.canvas, "lock_aspect", lock.get()))
        W.SettingRow(p, None, tr("SLOT_AREA_WINDOW_Label_Lock_Aspect_Ratio"), lock).pack(fill="x")

        W.section(p, "+").pack(anchor="w", pady=(8, 2))
        adds = ((SlotKind.PLAYING, "EDIT_LAYOUT_NL_Button_Add_Playing_Area_Slot"),
                (SlotKind.OBSERVER, "EDIT_LAYOUT_NL_Button_Add_Observer_Area_Slot"),
                (SlotKind.REPLAY, "EDIT_LAYOUT_NL_Button_Add_Replay_Area_Slot"),
                (SlotKind.LOBBY, "EDIT_LAYOUT_NL_Button_Add_Lobby_Slot"))
        dyn = ((SlotKind.ACTION_REQUIRED, "EDIT_LAYOUT_NL_Button_Add_Action_Required_Slot"),
               (SlotKind.QUEUE, "EDIT_LAYOUT_NL_Button_Add_Queue_Slot"),
               (SlotKind.IN_HAND, "EDIT_LAYOUT_NL_Button_Add_In_Hand_Slot"))
        for kind, key in adds:
            self._add_button(p, kind, key)
        W.section(p, tr("EDIT_LAYOUT_NL_Label_Dynamic_Slots")).pack(anchor="w", pady=(8, 2))
        for kind, key in dyn:
            self._add_button(p, kind, key)

        W.section(p, tr("EDIT_LAYOUT_NL_Label_Resize_Every_Slot")).pack(anchor="w", pady=(10, 2))
        sc = tk.Frame(p, bg=T.WINDOW_BG)
        sc.pack(anchor="w")
        W.label(sc, tr("EDIT_LAYOUT_NL_Label_Scale")).pack(side="left")
        self.scale = self._v(tk.IntVar(value=100))
        spin(sc, self.scale, 20, 300, 5, 5).pack(side="left", padx=4)
        W.label(sc, "%").pack(side="left")
        W.RoundButton(sc, "OK", self._apply_scale, kind="secondary", height=28, width=50).pack(side="left", padx=6)

        self.props = tk.Frame(p, bg=T.PRIMARY[50], padx=10, pady=8)
        self.props.pack(fill="x", pady=(12, 4), padx=(0, 10))
        self._select(None)
        self.after(50, self._changed)

    def _v(self, v):
        self.vars.append(v)
        return v

    def _set_switch_hotkey(self, hk: HotKey | None) -> bool:
        self.layout.switch_hotkey = str(hk) if hk else ""
        return True

    def _add_button(self, parent, kind: SlotKind, key: str):
        b = tk.Label(parent, text="＋  " + tr(key), bg=_light(SLOT_COLORS[kind], 0.8), fg=SLOT_COLORS[kind],
                     font=T.font(9, "bold"), anchor="w", padx=10, pady=6, cursor="hand2")
        b.pack(fill="x", pady=2, padx=(0, 10))
        b.bind("<Button-1>", lambda e: self._add(kind))

    def _add(self, kind: SlotKind):
        has = {s.kind for s in self.layout.slots}
        if kind in DYNAMIC_SLOT_KINDS and any(k in has for k in DYNAMIC_SLOT_KINDS if k != kind):
            W.info(self, tr("EDIT_LAYOUT_NL_Label_Dynamic_Slots"),
                   "Action Required / In Hand : un seul type de slot dynamique par layout.")
            return
        if kind == SlotKind.QUEUE and SlotKind.ACTION_REQUIRED not in has:
            W.info(self, tr("EDIT_LAYOUT_NL_Label_Dynamic_Slots"), tr("EDIT_LAYOUT_NL_Button_Add_Action_Required_Slot"))
            return
        s = self.screens[0]
        w = s.w // 3 if kind not in (SlotKind.LOBBY, SlotKind.QUEUE) else s.w // 5
        h = round(w / DEFAULT_TABLE_ASPECT)
        n = len(self.layout.slots)
        rect = Rect(s.x + (40 * n) % max(1, s.w - w), s.y + (30 * n) % max(1, s.h - h), w, h)
        capacity = 0 if kind in (SlotKind.OBSERVER, SlotKind.QUEUE) else 1
        slot = Slot(self.layout.next_slot_id(), kind, rect, capacity)
        self.layout.slots.append(slot)
        self.canvas.selected = slot
        self._select(slot)
        self._changed()

    def _changed(self):
        self.canvas.show(self.layout, self.layout.faults(self.screens))
        if self.canvas.selected is not None:
            self._select(self.canvas.selected, keep=True)

    def _select(self, slot: Slot | None, keep: bool = False):
        for w in self.props.winfo_children():
            w.destroy()
        bg = T.PRIMARY[50]
        if slot is None:
            W.label(self.props, "—", bg=bg, muted=True).pack(anchor="w")
            return
        labels = slot_labels()
        bold(self.props, f"{labels[slot.kind]} {self.layout.number_of(slot)}", bg=bg,
             fg=SLOT_COLORS[slot.kind], size=11).pack(anchor="w")
        grid = tk.Frame(self.props, bg=bg)
        grid.pack(anchor="w", pady=4)
        for i, (attr, key) in enumerate((("x", "SLOT_AREA_WINDOW_Label_PosX"), ("y", "SLOT_AREA_WINDOW_Label_PosY"),
                                         ("w", "SLOT_AREA_WINDOW_Label_Width"), ("h", "SLOT_AREA_WINDOW_Label_Height"))):
            W.label(grid, tr(key), bg=bg, size=9).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 4))
            v = self._v(tk.IntVar(value=getattr(slot.rect, attr)))
            spin(grid, v, -10000, 10000, 10, 6).grid(row=i // 2, column=(i % 2) * 2 + 1, padx=(0, 10), pady=2)

            def write(*_, attr=attr, v=v):
                try:
                    r = slot.rect
                    vals = {"x": r.x, "y": r.y, "w": r.w, "h": r.h, attr: int(v.get())}
                except (tk.TclError, ValueError):
                    return
                slot.rect = Rect(vals["x"], vals["y"], max(40, vals["w"]), max(30, vals["h"]))
                self.canvas.show(self.layout, self.layout.faults(self.screens))
            v.trace_add("write", write)
        if slot.kind in (SlotKind.PLAYING, SlotKind.OBSERVER, SlotKind.ACTION_REQUIRED, SlotKind.QUEUE,
                         SlotKind.IN_HAND, SlotKind.LOBBY):
            st = self._v(tk.BooleanVar(value=slot.stacks))
            text = tr("LOBBY_SLOT_AREA_WINDOW_Label_Stack_In_Slot") if slot.kind == SlotKind.LOBBY else "Stack ⧉"

            def set_stack(*_):
                slot.capacity = 0 if st.get() else 1
                self.canvas.draw()
            st.trace_add("write", set_stack)
            W.SettingRow(self.props, None, text, st, bg=bg).pack(fill="x")
        if slot.kind == SlotKind.LOBBY:
            W.label(self.props, tr("LOBBY_SLOT_AREA_WINDOW_Label_Select_Site"), bg=bg, bold=True).pack(anchor="w")
            site = self._v(tk.StringVar(value=slot.site or "*"))
            combo(self.props, site, ["*"] + [s.id for s in self.app.config.sites], 22).pack(anchor="w")
            site.trace_add("write", lambda *_: (setattr(slot, "site", "" if site.get() == "*" else site.get()),
                                                self.canvas.draw()))
            W.label(self.props, tr("LOBBY_SLOT_AREA_WINDOW_Label_Disclaimer"), bg=bg, muted=True, size=8,
                    wrap=280).pack(anchor="w", pady=(4, 0))
        W.RoundButton(self.props, "✕  " + tr("DIALOG_DELETE_LAYOUT_NL_Button_Delete"), lambda: self._delete(slot),
                      kind="danger", height=28, font_size=9).pack(anchor="w", pady=(8, 0))

    def _delete(self, slot: Slot):
        self.layout.slots.remove(slot)
        self.canvas.selected = None
        self._select(None)
        self._changed()

    def _apply_scale(self):
        try:
            k = self.scale.get() / 100
        except tk.TclError:
            return
        for s in self.layout.slots:
            s.rect = Rect(s.rect.x, s.rect.y, max(40, round(s.rect.w * k)), max(30, round(s.rect.h * k)))
        self.scale.set(100)
        self._changed()

    def _save(self):
        name = self.name_var.get().strip() or self.layout.name
        if any(l.name == name for l in self.app.config.layouts) and name != self.original_name:
            W.info(self, tr("EDIT_LAYOUT_NL_Label_Layout_Name"), f"« {name} » existe déjà.")
            return
        faults = self.layout.faults(self.screens)
        if faults:
            if not W.ask_yes_no(self, tr("EDIT_LAYOUT_NL_ON_EDIT_LAYOUT_SLOT_OUTSIDE_BOUNDS_Title"),
                                tr("EDIT_LAYOUT_NL_ON_EDIT_LAYOUT_SLOT_OUTSIDE_BOUNDS_Message"),
                                tr("EDIT_LAYOUT_NL_Button_Save_Changes"), tr("RNG_SETTINGS_Button_Cancel"), danger=True):
                return
            self.layout.slots = [s for s in self.layout.slots if s not in faults]
        self.layout.name = name
        self.page.close_editor(self.layout, self.original_name)
