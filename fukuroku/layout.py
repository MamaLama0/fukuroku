"""Layouts et emplacements (slots).

Types de slots du logiciel d'origine (``SlotType``) :

* PLAYING (jeu) et OBSERVER (observation) : emplacements « fixes » des tables ;
* ACTION_REQUIRED : slots dynamiques où une table passe quand c'est votre tour
  (une table à la fois ; si tous sont pris, les tables attendent dans les
  slots QUEUE puis montent dans l'ordre d'urgence) ;
* IN_HAND : slots dynamiques où passent les tables où vous êtes en main ;
* REPLAY : fenêtres de replay de main ;
* LOBBY : fenêtres de lobby (seule la position est appliquée).

Chaque emplacement peut empiler plusieurs tables (``capacity``, 0 = illimité).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from .geometry import Rect

# Ratio largeur/hauteur courant d'une table de poker (8:5 env.).
DEFAULT_TABLE_ASPECT = 1.4545


class SlotKind(str, Enum):
    PLAYING = "playing"
    OBSERVER = "observer"
    ACTION_REQUIRED = "action_required"
    QUEUE = "queue"
    IN_HAND = "in_hand"
    REPLAY = "replay"
    LOBBY = "lobby"


# Noms des types dans les fichiers de layout d'origine.
ORIGINAL_SLOT_TYPES = {"Playing": SlotKind.PLAYING, "Observer": SlotKind.OBSERVER,
                       "ActionRequired": SlotKind.ACTION_REQUIRED, "Queue": SlotKind.QUEUE,
                       "InHand": SlotKind.IN_HAND, "Replay": SlotKind.REPLAY, "Lobby": SlotKind.LOBBY}
TABLE_SLOT_KINDS = (SlotKind.PLAYING, SlotKind.OBSERVER, SlotKind.ACTION_REQUIRED, SlotKind.QUEUE, SlotKind.IN_HAND)
DYNAMIC_SLOT_KINDS = (SlotKind.ACTION_REQUIRED, SlotKind.IN_HAND)

# Couleurs des slots dans l'éditeur d'origine (icônes playing/observer/replay_slot).
SLOT_COLORS = {SlotKind.PLAYING: "#3CB869", SlotKind.OBSERVER: "#30268E", SlotKind.ACTION_REQUIRED: "#E33151",
               SlotKind.QUEUE: "#F3AE00", SlotKind.IN_HAND: "#7652F8", SlotKind.REPLAY: "#19ADFF",
               SlotKind.LOBBY: "#4B5057"}


@dataclass
class Slot:
    id: int
    kind: SlotKind
    rect: Rect
    capacity: int = 1
    site: str = ""  # slots LOBBY : salle dont le lobby va dans ce slot ("" = toutes)

    @property
    def stacks(self) -> bool:
        return self.capacity != 1

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind.value, "rect": self.rect.to_list(), "capacity": self.capacity}
        if self.site:
            d["site"] = self.site
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Slot":
        return cls(int(d["id"]), SlotKind(d.get("kind", "playing")), Rect.from_list(d["rect"]),
                   int(d.get("capacity", 1)), d.get("site", ""))


@dataclass
class Layout:
    name: str
    slots: list[Slot] = field(default_factory=list)
    table_aspect: float | None = DEFAULT_TABLE_ASPECT
    switch_hotkey: str = ""  # raccourci pour activer ce layout pendant la session
    stack_ar: bool = False  # empiler les tables dans le slot AR au fur et à mesure
    description: str = ""

    def slots_of(self, kind: SlotKind) -> list[Slot]:
        return sorted((s for s in self.slots if s.kind == kind), key=lambda s: s.id)

    @property
    def playing_slots(self) -> list[Slot]:
        return self.slots_of(SlotKind.PLAYING)

    @property
    def observer_slots(self) -> list[Slot]:
        return self.slots_of(SlotKind.OBSERVER)

    def slot(self, slot_id: int) -> Slot | None:
        return next((s for s in self.slots if s.id == slot_id), None)

    def has(self, kind: SlotKind) -> bool:
        return any(s.kind == kind for s in self.slots)

    def ordered_slots(self) -> list[Slot]:
        """Slots de tables dans l'ordre de parcours (jeu, observation, dynamiques)."""
        return [s for k in TABLE_SLOT_KINDS for s in self.slots_of(k)]

    def number_of(self, slot: Slot) -> int:
        """Numéro du slot dans son type (1..n), comme dans l'éditeur d'origine."""
        return self.slots_of(slot.kind).index(slot) + 1

    def next_slot_id(self) -> int:
        return max((s.id for s in self.slots), default=0) + 1

    def nearest_slot(self, rect: Rect, max_distance: float | None = None,
                     kinds: tuple[SlotKind, ...] = TABLE_SLOT_KINDS) -> Slot | None:
        best = min((s for s in self.slots if s.kind in kinds), key=lambda s: s.rect.distance_to(rect), default=None)
        if best is None:
            return None
        if max_distance is not None and best.rect.distance_to(rect) > max_distance:
            return None
        return best

    def slot_at(self, px: float, py: float) -> Slot | None:
        return next((s for s in self.ordered_slots() if s.rect.contains(px, py)), None)

    def placement_rect(self, slot: Slot) -> Rect:
        return slot.rect.fit_aspect(self.table_aspect)

    def bounds(self) -> Rect | None:
        if not self.slots:
            return None
        x, y = min(s.rect.x for s in self.slots), min(s.rect.y for s in self.slots)
        return Rect(x, y, max(s.rect.right for s in self.slots) - x, max(s.rect.bottom for s in self.slots) - y)

    def faults(self, screens: list[Rect]) -> list[Slot]:
        """Slots hors écran ou qui se chevauchent (bordure rouge dans l'éditeur d'origine)."""
        bad = []
        for s in self.slots:
            inside = any(sc.intersection(s.rect) and sc.intersection(s.rect).area >= 0.98 * s.rect.area for sc in screens)
            overlap = any(o is not s and o.kind == s.kind and s.rect.overlap_ratio(o.rect) > 0.5 for o in self.slots)
            if not inside or (overlap and s.kind not in (SlotKind.LOBBY,)):
                bad.append(s)
        return bad

    def to_dict(self) -> dict:
        return {"name": self.name, "table_aspect": self.table_aspect, "switch_hotkey": self.switch_hotkey,
                "stack_ar": self.stack_ar, "description": self.description,
                "slots": [s.to_dict() for s in self.slots]}

    @classmethod
    def from_dict(cls, d: dict) -> "Layout":
        return cls(d["name"], [Slot.from_dict(s) for s in d.get("slots", [])], d.get("table_aspect", DEFAULT_TABLE_ASPECT),
                   d.get("switch_hotkey", ""), bool(d.get("stack_ar", False)), d.get("description", ""))


# ---------------------------------------------------------------------- layouts prédéfinis d'origine
@dataclass
class PresetLayout:
    """Layout prédéfini du logiciel d'origine (PresetLayouts/<résolution>.json)."""

    description: str
    size: tuple[int, int]
    slots: list[tuple[SlotKind, Rect, int, str]]

    def build(self, name: str, screen: Rect) -> Layout:
        """Adapte le préréglage à l'écran choisi (mise à l'échelle proportionnelle)."""
        kx, ky = screen.w / self.size[0], screen.h / self.size[1]
        slots = []
        for i, (kind, r, capacity, site) in enumerate(self.slots, start=1):
            rect = Rect(screen.x + round(r.x * kx), screen.y + round(r.y * ky), round(r.w * kx), round(r.h * ky))
            slots.append(Slot(i, kind, rect, capacity, site))
        return Layout(name, slots, DEFAULT_TABLE_ASPECT, description=self.description)


def parse_original_presets(data: list[dict]) -> list[PresetLayout]:
    presets = []
    for p in data:
        w, h = (int(float(v)) for v in str(p["DisplayRequirements"]["Size"]).split(","))
        raw = sorted(p["Layout"]["Slots"], key=lambda s: (list(ORIGINAL_SLOT_TYPES).index(s["SlotType"])
                                                          if s["SlotType"] in ORIGINAL_SLOT_TYPES else 99, s["Id"]))
        slots = []
        for s in raw:
            kind = ORIGINAL_SLOT_TYPES.get(s["SlotType"])
            if kind is None:
                continue
            b = s["Bounds"]
            capacity = 0 if s.get("StackingOption") == "Stack" or kind in (SlotKind.OBSERVER, SlotKind.QUEUE) else 1
            slots.append((kind, Rect(round(b["X"]), round(b["Y"]), round(b["Width"]), round(b["Height"])),
                          capacity, s.get("Game", "")))
        presets.append(PresetLayout(p.get("Description", ""), (w, h), slots))
    return presets


def original_presets(directory: Path | None = None) -> dict[str, list[PresetLayout]]:
    """Préréglages d'origine par résolution (« 1920x1080 »…)."""
    if directory is None:
        from . import assets
        directory = assets.path("presets")
    out = {}
    for f in sorted(Path(directory).glob("*.json")):
        out[f.stem] = parse_original_presets(json.loads(f.read_text(encoding="utf-8")))
    return out


def presets_for(screen: Rect, directory: Path | None = None) -> list[PresetLayout]:
    """Préréglages compatibles avec l'écran (même orientation et même ratio, à 5 % près)."""
    found = []
    for presets in original_presets(directory).values():
        for p in presets:
            if (p.size[0] >= p.size[1]) == (screen.w >= screen.h) and \
                    abs(p.size[0] / p.size[1] - screen.w / max(1, screen.h)) < 0.05:
                found.append(p)
    return found


def grid_slots(area: Rect, cols: int, rows: int, kind: SlotKind, start_id: int = 1,
               gap: int = 0, capacity: int = 1) -> list[Slot]:
    """Découpe ``area`` en une grille cols×rows d'emplacements."""
    cols, rows = max(1, cols), max(1, rows)
    cw = (area.w - gap * (cols - 1)) / cols
    rh = (area.h - gap * (rows - 1)) / rows
    slots = []
    for r in range(rows):
        for c in range(cols):
            x = area.x + round(c * (cw + gap))
            y = area.y + round(r * (rh + gap))
            slots.append(Slot(start_id + len(slots), kind, Rect(x, y, round(cw), round(rh)), capacity))
    return slots


def grid_layout(name: str, screens: list[Rect], cols: int, rows: int, aspect: float | None = DEFAULT_TABLE_ASPECT,
                gap: int = 0) -> Layout:
    """Layout « grille » : chaque écran est découpé de la même façon, tout en zone de jeu."""
    slots: list[Slot] = []
    for screen in screens:
        slots += grid_slots(screen, cols, rows, SlotKind.PLAYING, len(slots) + 1, gap)
    return Layout(name, slots, aspect)


def best_grid(area: Rect, n: int, aspect: float = DEFAULT_TABLE_ASPECT) -> tuple[int, int]:
    """Grille cols×rows qui maximise la taille des tables pour n tables."""
    best, best_size = (1, max(1, n)), -1.0
    for cols in range(1, max(1, n) + 1):
        rows = math.ceil(n / cols)
        cell = Rect(0, 0, area.w // cols, area.h // rows).fit_aspect(aspect)
        if cell.area > best_size:
            best, best_size = (cols, rows), cell.area
    return best


def auto_layout(name: str, screens: list[Rect], n_tables: int, aspect: float = DEFAULT_TABLE_ASPECT,
                observer_ratio: float = 0.0) -> Layout:
    """Création automatique (« Create New Layout Automatically »).

    Répartit ``n_tables`` sur les écrans proportionnellement à leur surface.
    Avec ``observer_ratio`` > 0, une bande du dernier écran est réservée à la
    zone d'observation, où les tables sont empilées.
    """
    screens = screens or [Rect(0, 0, 1920, 1080)]
    total = sum(s.area for s in screens) or 1
    remaining = n_tables
    slots: list[Slot] = []
    for i, screen in enumerate(screens):
        area = screen
        if observer_ratio > 0 and i == len(screens) - 1:
            obs_h = round(screen.h * observer_ratio)
            area = Rect(screen.x, screen.y, screen.w, screen.h - obs_h)
            obs_area = Rect(screen.x, screen.y + screen.h - obs_h, screen.w, obs_h)
        count = remaining if i == len(screens) - 1 else max(1, round(n_tables * screen.area / total))
        count = max(0, min(count, remaining))
        remaining -= count
        if count:
            cols, rows = best_grid(area, count, aspect)
            cells = grid_slots(area, cols, rows, SlotKind.PLAYING, len(slots) + 1)[:count]
            slots += cells
        if observer_ratio > 0 and i == len(screens) - 1:
            n_obs = max(1, round(obs_area.w / (obs_area.h * aspect)))
            slots += grid_slots(obs_area, n_obs, 1, SlotKind.OBSERVER, len(slots) + 1, capacity=0)
    return Layout(name, slots, aspect)


def cascade_layout(name: str, screen: Rect, n_tables: int, table_size: tuple[int, int] = (640, 440),
                   step: tuple[int, int] = (40, 30)) -> Layout:
    """Layout « cascade » : tables décalées en diagonale."""
    slots = []
    w, h = table_size
    for i in range(n_tables):
        x = screen.x + (i * step[0]) % max(1, screen.w - w)
        y = screen.y + (i * step[1]) % max(1, screen.h - h)
        slots.append(Slot(i + 1, SlotKind.PLAYING, Rect(x, y, w, h)))
    return Layout(name, slots, None)


def stacked_layout(name: str, screen: Rect, playing: int = 1, aspect: float = DEFAULT_TABLE_ASPECT) -> Layout:
    """Layout « pile » : peu d'emplacements de jeu, chacun empile un nombre illimité de tables."""
    cols, rows = best_grid(screen, playing, aspect)
    slots = grid_slots(screen, cols, rows, SlotKind.PLAYING, capacity=0)[:playing]
    return Layout(name, slots, aspect)


PRESETS = {
    "grid": "Grille",
    "auto": "Automatique",
    "auto_observer": "Automatique + zone d'observation",
    "stack": "Pile",
    "cascade": "Cascade",
}


def build_preset(kind: str, name: str, screens: list[Rect], n_tables: int = 4, cols: int = 2, rows: int = 2,
                 aspect: float = DEFAULT_TABLE_ASPECT) -> Layout:
    if kind == "grid":
        return grid_layout(name, screens, cols, rows, aspect)
    if kind == "auto":
        return auto_layout(name, screens, n_tables, aspect)
    if kind == "auto_observer":
        return auto_layout(name, screens, n_tables, aspect, observer_ratio=0.25)
    if kind == "stack":
        return stacked_layout(name, screens[0], max(1, n_tables), aspect)
    if kind == "cascade":
        return cascade_layout(name, screens[0], n_tables)
    raise ValueError(f"preset inconnu : {kind}")
