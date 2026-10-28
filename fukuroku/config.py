"""Configuration locale (JSON), sauvegarde/restauration.

Les sections reprennent les pages du logiciel d'origine (Configuration
générale, Bordure de table, Raccourcis, Contrôleur, Temps de session,
Overlays, Changement automatique de layout).  La sauvegarde « cloud »
d'origine (ConfigCloudBackupService / S3) est remplacée par un export/import
de fichier local.  Rien n'est envoyé sur le réseau.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .betsizing import DEFAULT_BET_BUTTONS, BetButton, RaiseMode
from .geometry import Rect
from .hotkeys import HotKeyRegistry, default_registry
from .layout import Layout, auto_layout, grid_layout, presets_for
from .placement import PlacementSettings
from .rng import RngSettings
from .sites import SiteDefinition, default_sites

CONFIG_VERSION = 2


def config_dir() -> Path:
    override = os.environ.get("FUKUROKU_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Fukuroku"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Fukuroku"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "fukuroku"


class _Section:
    """Sérialisation commune : champs simples, valeurs inconnues ignorées."""

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    @classmethod
    def from_dict(cls, d: dict):
        s = cls()
        for f in dataclasses.fields(cls):
            if f.name in d:
                setattr(s, f.name, d[f.name])
        return s


@dataclass
class GeneralSettings(_Section):
    language: str = "fr"
    # Paramètres globaux
    minimize_to_tray: bool = False
    focus_follows_mouse: bool = False  # « Mettre la table sous le curseur au premier plan »
    bring_only_playing_to_front: bool = False
    force_mouse_move: bool = False  # avec l'auto-focus de la table la plus urgente
    hide_table_titles: bool = False
    show_rng: bool = False
    # Alarmes « action requise »
    ar_sound_enabled: bool = True
    ar_sound: str = "Bell"
    ar_volume: float = 0.8
    delayed_alarm_enabled: bool = False
    delayed_alarm_seconds: int = 10
    delayed_alarm_sound: str = "Ascending"
    delayed_alarm_volume: float = 1.0
    # Divers (Fukuroku)
    poll_interval_ms: int = 250
    action_delay_ms: int = 30
    decimal_comma: bool = False
    start_minimized: bool = False
    bb_mode: bool = False
    break_every_min: int = 0
    session_log: bool = True

    @classmethod
    def from_dict(cls, d: dict):
        s = super().from_dict(d)
        if s.ar_sound in ("Cloche", "Montée", "Bulle", "Ping", "Double", "Grave"):  # sons de la 1.0
            s.ar_sound = "Bell"
        return s


@dataclass
class BorderSettings(_Section):
    """Onglet « Bordure de table »."""

    enabled: bool = False
    mode: str = "transition"  # "transition" (vert → jaune → rouge) | "colors"
    color_start: str = "#3CB869"
    color_end: str = "#E33151"
    last_seconds: int = 5
    turn_seconds: int = 15  # durée estimée d'un tour (le client n'est pas lu)
    blink: bool = False
    only_most_urgent: bool = False
    highlight_focused: bool = False
    focused_color: str = "#7652F8"
    size: int = 4


@dataclass
class HotkeySettings(_Section):
    """Onglets « Boutons de mise » et « Paramètres » de la page Raccourcis."""

    target: str = "hovered"  # "hovered" (table sous le pointeur) | "focused"
    wheel_betting: bool = False
    wheel_step: str = "bb"  # "sb" | "bb"
    bet_step_bb: float = 0.5
    instant_shove_hotkey: bool = False
    instant_shove_overlay: bool = False
    instant_shove_allin_only: bool = False
    ctrl_switches_groups: bool = True
    bet_buttons: list = field(default_factory=lambda: [BetButton(**b.to_dict()) for b in DEFAULT_BET_BUTTONS])
    raise_mode: RaiseMode = field(default_factory=RaiseMode)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["bet_buttons"] = [b.to_dict() for b in self.bet_buttons]
        d["raise_mode"] = self.raise_mode.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict):
        s = super().from_dict(d)
        s.bet_buttons = [BetButton.from_dict(b) for b in d.get("bet_buttons", [])] or \
            [BetButton(**b.to_dict()) for b in DEFAULT_BET_BUTTONS]
        s.raise_mode = RaiseMode.from_dict(d.get("raise_mode", {}))
        return s


@dataclass
class ControllerSettings(_Section):
    enabled: bool = False
    vibrate_on_turn: bool = True
    cursor_speed: int = 5  # 1 (vraiment lent) … 10 (super rapide)


@dataclass
class SessionSettings(_Section):
    """Page « Temps de session »."""

    timer_enabled: bool = True
    show_timer_widget: bool = False
    stop_when_all_closed: bool = True
    closed_grace_5min: bool = False
    start_mode: str = "first_table"  # "first_dealt" | "first_table" | "manual"
    minimize_widget_on_start: bool = False
    show_open_tables_widget: bool = False
    show_ar_tables_widget: bool = False
    show_hands_widget: bool = False
    count_type: str = "all"  # all | spin | tournament | cash
    notify_hands_enabled: bool = False
    notify_hands: int = 500
    notify_tables_enabled: bool = False
    notify_tables: int = 50
    widget_positions: dict = field(default_factory=dict)


@dataclass
class OverlaySettings(_Section):
    """Page « Overlays pour tables »."""

    move_with_ctrl: bool = False
    size: str = "medium"  # small | medium | big
    opacity: float = 0.9
    ar_counter: bool = False
    st_counter: bool = False
    bet_buttons: bool = False
    bet_buttons_count: int = 4
    bet_buttons_last_allin: bool = False
    bet_buttons_always_visible: bool = False
    screenshot: bool = False
    screenshot_folder: str = ""
    # Overlays alimentés par un fournisseur de données de table
    pot_odds: bool = False
    pot_odds_ratio: bool = False
    spr: bool = False
    effs: bool = False
    mdf: bool = False
    outs: bool = False
    bluff_equity: bool = False
    spr_next_street: bool = False
    pot_next_street: bool = False
    positions: bool = False
    action_history: bool = False
    hide_board: bool = False
    hand_counter: bool = False
    positions_offsets: dict = field(default_factory=dict)


@dataclass
class AutoSwitchSettings(_Section):
    """Onglet « Changement Auto Layout » : layout selon le nombre de tables ouvertes."""

    enabled: bool = False
    initial_layout: str = ""
    rules: list = field(default_factory=list)  # [[nb_tables, nom_layout], …]
    go_back_on_decrease: bool = True
    ask_before: bool = False

    def layout_for(self, n_tables: int) -> str | None:
        """Layout à activer pour ``n_tables`` (règle au seuil le plus haut atteint)."""
        best = None
        for n, name in sorted((int(n), name) for n, name in self.rules):
            if n_tables >= n:
                best = name
        return best or (self.initial_layout or None)


@dataclass
class Config:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    placement: PlacementSettings = field(default_factory=PlacementSettings)
    border: BorderSettings = field(default_factory=BorderSettings)
    hotkey_settings: HotkeySettings = field(default_factory=HotkeySettings)
    controller: ControllerSettings = field(default_factory=ControllerSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
    overlays: OverlaySettings = field(default_factory=OverlaySettings)
    auto_switch: AutoSwitchSettings = field(default_factory=AutoSwitchSettings)
    layouts: list[Layout] = field(default_factory=list)
    active_layout: str = ""
    sites: list[SiteDefinition] = field(default_factory=default_sites)
    hotkeys: HotKeyRegistry = field(default_factory=default_registry)
    rng: RngSettings = field(default_factory=RngSettings)
    ignored_titles: list[str] = field(default_factory=list)

    # ----------------------------------------------------------------- layouts
    def layout(self, name: str | None = None) -> Layout | None:
        name = name or self.active_layout
        return next((l for l in self.layouts if l.name == name), self.layouts[0] if self.layouts else None)

    def ensure_layouts(self, screens: list[Rect]) -> None:
        if not self.layouts:
            main = screens[0] if screens else Rect(0, 0, 1920, 1080)
            presets = presets_for(main)
            if presets:  # préréglages d'origine adaptés à l'écran principal
                wanted = [p for p in presets if "6 playing slots mosaic" in p.description] or presets[:1]
                self.layouts.append(wanted[0].build("Layout 1", main))
            self.layouts += [auto_layout(f"Layout {len(self.layouts) + 1}", screens, 4),
                             grid_layout(f"Layout {len(self.layouts) + 2}", screens[:1], 3, 3)]
        if not self.active_layout or not any(l.name == self.active_layout for l in self.layouts):
            self.active_layout = self.layouts[0].name

    def next_layout_name(self) -> str:
        names = [l.name for l in self.layouts]
        if not names:
            return ""
        i = names.index(self.active_layout) if self.active_layout in names else -1
        return names[(i + 1) % len(names)]

    def site(self, site_id: str) -> SiteDefinition | None:
        return next((s for s in self.sites if s.id == site_id), None)

    # ----------------------------------------------------------------- (dé)sérialisation
    def to_dict(self) -> dict:
        return {
            "version": CONFIG_VERSION,
            "general": self.general.to_dict(),
            "placement": self.placement.to_dict(),
            "border": self.border.to_dict(),
            "hotkey_settings": self.hotkey_settings.to_dict(),
            "controller": self.controller.to_dict(),
            "session": self.session.to_dict(),
            "overlays": self.overlays.to_dict(),
            "auto_switch": self.auto_switch.to_dict(),
            "layouts": [l.to_dict() for l in self.layouts],
            "active_layout": self.active_layout,
            "sites": [s.to_dict() for s in self.sites],
            "hotkeys": self.hotkeys.to_dict(),
            "rng": self.rng.to_dict(),
            "ignored_titles": self.ignored_titles,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        c = cls()
        g = d.get("general", {})
        c.general = GeneralSettings.from_dict(g)
        c.placement = PlacementSettings.from_dict(d.get("placement", {}))
        c.border = BorderSettings.from_dict(d.get("border", {}))
        c.hotkey_settings = HotkeySettings.from_dict(d.get("hotkey_settings", {}))
        if "bet_sizes" in d and "hotkey_settings" not in d:  # configuration 1.0
            c.hotkey_settings.bet_buttons = [BetButton.from_dict(b) for b in d["bet_sizes"]]
        if "hotkey_target" in g and "hotkey_settings" not in d:
            c.hotkey_settings.target = "focused" if g["hotkey_target"] == "focused" else "hovered"
        c.controller = ControllerSettings.from_dict(d.get("controller", {"enabled": g.get("gamepad_enabled", False)}))
        c.session = SessionSettings.from_dict(d.get("session", {}))
        c.overlays = OverlaySettings.from_dict(d.get("overlays", {}))
        c.auto_switch = AutoSwitchSettings.from_dict(d.get("auto_switch", {}))
        c.layouts = [Layout.from_dict(l) for l in d.get("layouts", [])]
        c.active_layout = d.get("active_layout", "")
        if "sites" in d:
            known = {s["id"]: SiteDefinition.from_dict(s) for s in d["sites"]}
            # Les salles ajoutées dans une version plus récente restent disponibles.
            c.sites = [known.pop(s.id, s) for s in default_sites()] + list(known.values())
        if "hotkeys" in d:
            c.hotkeys = HotKeyRegistry.from_dict(d["hotkeys"])
        c.rng = RngSettings.from_dict(d.get("rng", {}))
        c.ignored_titles = list(d.get("ignored_titles", []))
        return c

    # ----------------------------------------------------------------- fichiers
    @staticmethod
    def default_path() -> Path:
        return config_dir() / "config.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or cls.default_path()
        if not path.exists():
            return cls()
        with path.open(encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save(self, path: Path | None = None) -> Path:
        path = path or self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return path

    def export_to(self, path: Path) -> Path:
        """Export des paramètres (fichier .zip comme l'original, ou .json)."""
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("config.json", json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
            return path
        return self.save(path)

    @classmethod
    def import_from(cls, path: Path) -> "Config":
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as z:
                return cls.from_dict(json.loads(z.read("config.json").decode("utf-8")))
        return cls.load(path)
