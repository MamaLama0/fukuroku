"""Moteur de placement des tables (cœur « Placement Orchestrator »).

Moteur pur, sans effet de bord : chaque opération renvoie une liste de
commandes (déplacer, mettre au premier plan, donner le focus…) qu'un
contrôleur applique ensuite via le backend de la plateforme.  Cela permet de
tester toute la logique sans fenêtres réelles.

Comportements reproduits :
* nouvelle table → zone de jeu, zone d'observation ou rien (réglage par salle) ;
* slots dynamiques « Action requise » : la table où c'est votre tour y passe
  (une à la fois), les suivantes attendent dans les slots « Queue » et montent
  par ordre d'urgence ; après votre action la table revient à son slot d'avant ;
* slots dynamiques « In Hand » : la table y reste tant que vous êtes en main ;
* urgence de pile : dans un slot empilé, la table la plus urgente passe devant ;
* aimantation par zone (jeu, observation, lobby) avec échange si le slot est pris ;
* réordonnancement des zones quand une table est fermée ;
* fenêtres de lobby (position seulement) et de replay dans leurs slots ;
* déplacement vers le slot suivant/précédent (avec ou sans échange), envoi
  vers un slot numéroté, verrouillage hors du flux dynamique, cycle des tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable

from .geometry import Rect
from .layout import Layout, Slot, SlotKind
from .sites import Stakes

TABLE, LOBBY, REPLAY = "table", "lobby", "replay"
STATIC_KINDS = (SlotKind.PLAYING, SlotKind.OBSERVER)


@dataclass
class TableState:
    handle: Hashable
    site_id: str
    title: str
    rect: Rect
    arrival: float = 0.0
    slot_id: int | None = None
    needs_action: bool = False
    action_since: float | None = None
    locked: bool = False
    stakes: Stakes | None = None
    minimized: bool = False
    role: str = TABLE  # "table" | "lobby" | "replay"
    home_slot_id: int | None = None  # slot fixe d'origine pendant un passage en slot dynamique
    in_hand: bool = False

    @property
    def aspect(self) -> float | None:
        return self.rect.w / self.rect.h if self.rect.h else None


@dataclass(frozen=True)
class Move:
    handle: Hashable
    rect: Rect


@dataclass(frozen=True)
class Raise:
    handle: Hashable


@dataclass(frozen=True)
class Focus:
    handle: Hashable


Command = Any  # Move | Raise | Focus


@dataclass
class PlacementSettings:
    tiling: bool = True  # placement automatique activé
    stack_urgency: bool = True  # « Gérer l'urgence du stack »
    magnetize_playing: bool = True
    magnetize_observer: bool = True
    magnetize_lobby: bool = True
    invert_ctrl: bool = False  # aimanter seulement avec Ctrl enfoncé
    magnet_distance: int = 250
    reorder_playing_on_close: bool = False
    reorder_observer_on_close: bool = True
    auto_focus_urgent: bool = False
    return_to_previous_slot: bool = True  # après une action en slot AR
    ar_from_observer_only: bool = False
    dynamic_flow: bool = False  # sans slots dynamiques : observation → jeu quand c'est votre tour (Fukuroku)
    prioritize_higher_stakes: bool = False
    keep_table_aspect: bool = True

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "PlacementSettings":
        s = cls()
        if "magnetize" in d:  # configuration 1.0
            s.magnetize_playing = s.magnetize_observer = bool(d["magnetize"])
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


@dataclass
class PlacementEngine:
    layout: Layout
    settings: PlacementSettings = field(default_factory=PlacementSettings)
    tables: dict[Hashable, TableState] = field(default_factory=dict)

    # ------------------------------------------------------------------ requêtes
    def poker_tables(self) -> list[TableState]:
        return [t for t in self.tables.values() if t.role == TABLE]

    def occupants(self, slot_id: int) -> list[TableState]:
        """Fenêtres d'un slot, de la plus urgente à la moins urgente."""
        items = [t for t in self.tables.values() if t.slot_id == slot_id]
        return sorted(items, key=self._urgency_key)

    def _urgency_key(self, t: TableState):
        waiting = t.needs_action and t.action_since is not None
        stake = -(t.stakes.big_blind if (t.stakes and self.settings.prioritize_higher_stakes) else 0)
        return (0 if waiting else 1, stake, t.action_since if waiting else 0, t.arrival)

    def slot_of(self, handle) -> Slot | None:
        t = self.tables.get(handle)
        return self.layout.slot(t.slot_id) if t and t.slot_id is not None else None

    def kind_of(self, handle) -> SlotKind | None:
        slot = self.slot_of(handle)
        return slot.kind if slot else None

    def _has_room(self, slot: Slot, extra: int = 0) -> bool:
        return slot.capacity == 0 or len(self.occupants(slot.id)) + extra < slot.capacity

    def free_slot(self, kind: SlotKind, exclude: set[int] | None = None) -> Slot | None:
        candidates = [s for s in self.layout.slots_of(kind) if s.id not in (exclude or set()) and self._has_room(s)]
        if not candidates:
            return None
        return min(candidates, key=lambda s: (len(self.occupants(s.id)), s.id))

    def least_loaded_slot(self, kind: SlotKind) -> Slot | None:
        slots = self.layout.slots_of(kind)
        return min(slots, key=lambda s: (len(self.occupants(s.id)), s.id)) if slots else None

    def waiting_tables(self) -> list[TableState]:
        return sorted((t for t in self.poker_tables() if t.needs_action), key=self._urgency_key)

    def most_urgent(self) -> TableState | None:
        waiting = self.waiting_tables()
        return waiting[0] if waiting else None

    def ordered_tables(self) -> list[TableState]:
        """Ordre de cycle : par slot puis par arrivée."""
        order = {s.id: i for i, s in enumerate(self.layout.ordered_slots())}
        return sorted(self.poker_tables(), key=lambda t: (order.get(t.slot_id, 10_000), t.arrival))

    def stacked_count(self) -> int:
        """Nombre de tables cachées derrière une autre dans un slot empilé (compteur ST)."""
        return sum(max(0, len([t for t in self.poker_tables() if t.slot_id == s.id]) - 1) for s in self.layout.slots)

    # ------------------------------------------------------------------ helpers
    def _place(self, t: TableState, slot: Slot) -> list[Command]:
        t.slot_id = slot.id
        if slot.kind == SlotKind.LOBBY:  # lobby : seule la position est appliquée
            rect = Rect(slot.rect.x, slot.rect.y, t.rect.w, t.rect.h)
        else:
            aspect = (t.aspect or self.layout.table_aspect) if self.settings.keep_table_aspect else None
            rect = slot.rect.fit_aspect(aspect)
        t.rect = rect
        return [Move(t.handle, rect)]

    def _raise_top(self, slot_id: int | None) -> list[Command]:
        if slot_id is None or not self.settings.stack_urgency:
            return []
        occ = self.occupants(slot_id)
        return [Raise(occ[0].handle)] if len(occ) > 1 else []

    def _is_dynamic(self, slot_id: int | None) -> bool:
        slot = self.layout.slot(slot_id) if slot_id is not None else None
        return bool(slot and slot.kind in (SlotKind.ACTION_REQUIRED, SlotKind.QUEUE, SlotKind.IN_HAND))

    def _static_slot_for(self, t: TableState, prefer: SlotKind = SlotKind.PLAYING) -> Slot | None:
        other = SlotKind.OBSERVER if prefer == SlotKind.PLAYING else SlotKind.PLAYING
        for kind in (prefer, other):
            slot = self.free_slot(kind)
            if slot:
                return slot
        # Plus de place : on empile sur le slot le moins chargé.
        return self.least_loaded_slot(prefer) or self.least_loaded_slot(other)

    def _go_home(self, t: TableState) -> list[Command]:
        """Retour au slot d'avant un passage en slot dynamique."""
        home = self.layout.slot(t.home_slot_id) if t.home_slot_id is not None else None
        t.slot_id = None
        if home is None or not self.settings.return_to_previous_slot:
            home = self._static_slot_for(t, SlotKind.OBSERVER if self.layout.observer_slots else SlotKind.PLAYING)
        t.home_slot_id = None
        return self._place(t, home) if home else []

    def _enter_dynamic(self, t: TableState, slot: Slot) -> list[Command]:
        if not self._is_dynamic(t.slot_id):
            t.home_slot_id = t.slot_id
        return self._place(t, slot) + [Raise(t.handle)]

    # ------------------------------------------------------------------ événements
    def add_table(self, t: TableState, target: str = "playing") -> list[Command]:
        """Nouvelle fenêtre ; ``target`` = "playing" | "observer" | "nothing" (tables seulement)."""
        self.tables[t.handle] = t
        if not self.settings.tiling:
            return []
        if t.role == LOBBY:
            slots = [s for s in self.layout.slots_of(SlotKind.LOBBY) if not s.site or s.site == t.site_id]
            slots = [s for s in slots if self._has_room(s)] or slots
            return self._place(t, slots[0]) if slots else []
        if t.role == REPLAY:
            slot = self.free_slot(SlotKind.REPLAY) or self.least_loaded_slot(SlotKind.REPLAY)
            return self._place(t, slot) + [Raise(t.handle)] if slot else []
        if target == "nothing":
            return []
        prefer = SlotKind.OBSERVER if target == "observer" and self.layout.observer_slots else SlotKind.PLAYING
        slot = self._static_slot_for(t, prefer)
        if slot is None:
            return []
        cmds = self._place(t, slot) + [Raise(t.handle)]
        if t.needs_action:
            t.needs_action = False
            cmds += self.set_action_required(t.handle, True, t.action_since or t.arrival)
        return cmds

    def remove_table(self, handle) -> list[Command]:
        t = self.tables.pop(handle, None)
        if t is None:
            return []
        cmds = self._raise_top(t.slot_id)
        slot = self.layout.slot(t.slot_id) if t.slot_id is not None else None
        if slot is None:
            return cmds
        if slot.kind in (SlotKind.ACTION_REQUIRED, SlotKind.QUEUE):
            cmds += self._promote_queue()
        elif slot.kind == SlotKind.IN_HAND:
            cmds += self._promote_in_hand()
        elif slot.kind == SlotKind.PLAYING:
            if self.settings.reorder_playing_on_close:
                cmds += self.reorder(SlotKind.PLAYING)
            cmds += self._promote_waiting()
        elif slot.kind == SlotKind.OBSERVER and self.settings.reorder_observer_on_close:
            cmds += self.reorder(SlotKind.OBSERVER)
        return cmds

    def set_action_required(self, handle, required: bool, now: float) -> list[Command]:
        t = self.tables.get(handle)
        if t is None or t.role != TABLE or t.needs_action == required:
            return []
        t.needs_action = required
        t.action_since = now if required else None
        cmds: list[Command] = []
        has_ar = self.layout.has(SlotKind.ACTION_REQUIRED)
        if required:
            if has_ar and not t.locked:
                cmds += self._to_action_required(t)
            elif self.layout.has(SlotKind.IN_HAND) and not t.locked and not t.in_hand:
                t.in_hand = True
                cmds += self._to_in_hand(t)
            elif self.settings.dynamic_flow and not t.locked and self.kind_of(handle) == SlotKind.OBSERVER:
                slot = self.free_slot(SlotKind.PLAYING)
                if slot:
                    t.home_slot_id = t.slot_id
                    cmds += self._place(t, slot)
            cmds += self._raise_top(t.slot_id) or [Raise(handle)]
            if self.settings.auto_focus_urgent:
                urgent = self.most_urgent()
                if urgent:
                    cmds.append(Focus(urgent.handle))
        else:
            kind = self.kind_of(handle)
            old_slot = t.slot_id
            if kind in (SlotKind.ACTION_REQUIRED, SlotKind.QUEUE):
                cmds += self._go_home(t) + self._raise_top(old_slot) + self._promote_queue()
            elif self.settings.dynamic_flow and t.home_slot_id is not None and not t.locked:
                cmds += self._go_home(t) + self._raise_top(old_slot) + self._promote_waiting()
            else:
                cmds += self._raise_top(old_slot)
            if self.settings.auto_focus_urgent:
                urgent = self.most_urgent()
                if urgent:
                    cmds.append(Focus(urgent.handle))
        return cmds

    def _to_action_required(self, t: TableState) -> list[Command]:
        if self.kind_of(t.handle) == SlotKind.ACTION_REQUIRED:
            return []
        if self.settings.ar_from_observer_only and self.kind_of(t.handle) == SlotKind.PLAYING:
            return []
        slot = self.free_slot(SlotKind.ACTION_REQUIRED)
        if slot is None and self.layout.stack_ar:
            slot = self.least_loaded_slot(SlotKind.ACTION_REQUIRED)
        if slot is None:
            if self.kind_of(t.handle) == SlotKind.QUEUE:
                return []
            slot = self.free_slot(SlotKind.QUEUE) or self.least_loaded_slot(SlotKind.QUEUE)
            if slot is None:
                return []  # pas de file : la table attend dans son slot
        return self._enter_dynamic(t, slot)

    def _promote_queue(self) -> list[Command]:
        """Un slot AR s'est libéré : la table la plus urgente en attente y monte."""
        cmds: list[Command] = []
        for t in self.waiting_tables():
            if t.locked or self.kind_of(t.handle) == SlotKind.ACTION_REQUIRED:
                continue
            slot = self.free_slot(SlotKind.ACTION_REQUIRED)
            if slot is None:
                break
            old = t.slot_id
            cmds += self._enter_dynamic(t, slot) + self._raise_top(old)
        return cmds

    def set_in_hand(self, handle, in_hand: bool) -> list[Command]:
        """Fournisseur de données / sonde : le héros est (ou n'est plus) en main sur cette table."""
        t = self.tables.get(handle)
        if t is None or t.role != TABLE or t.in_hand == in_hand:
            return []
        t.in_hand = in_hand
        if not self.layout.has(SlotKind.IN_HAND) or t.locked:
            return []
        if in_hand:
            return self._to_in_hand(t)
        if self.kind_of(handle) != SlotKind.IN_HAND:
            return []
        old = t.slot_id
        return self._go_home(t) + self._raise_top(old) + self._promote_in_hand()

    def _to_in_hand(self, t: TableState) -> list[Command]:
        if self.kind_of(t.handle) == SlotKind.IN_HAND:
            return []
        slot = self.free_slot(SlotKind.IN_HAND)
        return self._enter_dynamic(t, slot) if slot else []

    def _promote_in_hand(self) -> list[Command]:
        cmds: list[Command] = []
        for t in sorted((t for t in self.poker_tables() if t.in_hand and not t.locked), key=self._urgency_key):
            if self.kind_of(t.handle) == SlotKind.IN_HAND:
                continue
            slot = self.free_slot(SlotKind.IN_HAND)
            if slot is None:
                break
            cmds += self._enter_dynamic(t, slot)
        return cmds

    def _promote_waiting(self) -> list[Command]:
        """Flux observation → jeu (Fukuroku) : une place de jeu s'est libérée."""
        if not self.settings.dynamic_flow or self.layout.has(SlotKind.ACTION_REQUIRED):
            return []
        cmds: list[Command] = []
        for t in self.waiting_tables():
            if t.locked or self.kind_of(t.handle) != SlotKind.OBSERVER:
                continue
            slot = self.free_slot(SlotKind.PLAYING)
            if slot is None:
                break
            t.home_slot_id = t.slot_id
            cmds += self._place(t, slot) + [Raise(t.handle)]
        return cmds

    def user_moved(self, handle, rect: Rect, ctrl: bool = False) -> list[Command]:
        """Aimantation (Magnetizer) après un déplacement manuel ; échange si le slot est pris."""
        t = self.tables.get(handle)
        if t is None:
            return []
        old_slot = self.layout.slot(t.slot_id) if t.slot_id is not None else None
        t.rect = rect
        active = ctrl if self.settings.invert_ctrl else not ctrl
        s = self.settings
        if t.role == LOBBY:
            kinds = (SlotKind.LOBBY,) if s.magnetize_lobby else ()
        else:
            kinds = tuple(k for k, on in ((SlotKind.PLAYING, s.magnetize_playing),
                                          (SlotKind.OBSERVER, s.magnetize_observer),
                                          (SlotKind.REPLAY, t.role == REPLAY)) if on)
        slot = self.layout.nearest_slot(rect, s.magnet_distance, kinds) if (active and kinds) else None
        if slot is None:
            t.slot_id = None
            t.home_slot_id = None
            return []
        cmds: list[Command] = []
        if not self._has_room(slot, extra=0) and old_slot is not None and old_slot.id != slot.id:
            other = next((o for o in self.occupants(slot.id) if o.handle != handle), None)
            if other is not None:
                cmds += self._place(other, old_slot)
        t.home_slot_id = None
        return cmds + self._place(t, slot) + [Raise(handle)]

    # ------------------------------------------------------------------ actions utilisateur
    def send_to_area(self, handle, kind: SlotKind) -> list[Command]:
        t = self.tables.get(handle)
        if t is None:
            return []
        slot = self.free_slot(kind) or self.least_loaded_slot(kind)
        if slot is None or slot.id == t.slot_id:
            return []
        old = t.slot_id
        t.home_slot_id = None
        return self._place(t, slot) + [Raise(handle)] + self._raise_top(old)

    def send_to_slot(self, handle, kind: SlotKind, index: int, swap: bool = True) -> list[Command]:
        """Envoie la table dans le slot n° ``index`` (1..n) de la zone donnée."""
        slots = self.layout.slots_of(kind)
        if not 1 <= index <= len(slots):
            return []
        return self._move_to(handle, slots[index - 1], swap)

    def _move_to(self, handle, target: Slot, swap: bool) -> list[Command]:
        t = self.tables.get(handle)
        if t is None or t.slot_id == target.id:
            return []
        old_slot = self.layout.slot(t.slot_id) if t.slot_id is not None else None
        cmds: list[Command] = []
        if swap and not self._has_room(target) and old_slot is not None:
            other = self.occupants(target.id)[0]
            cmds += self._place(other, old_slot)
        t.home_slot_id = None
        cmds += self._place(t, target) + [Raise(handle)]
        if old_slot is not None:
            cmds += self._raise_top(old_slot.id)
        return cmds

    def move_to_adjacent_slot(self, handle, step: int, swap: bool = False) -> list[Command]:
        t = self.tables.get(handle)
        slots = [s for k in STATIC_KINDS for s in self.layout.slots_of(k)]
        if t is None or not slots:
            return []
        ids = [s.id for s in slots]
        idx = ids.index(t.slot_id) if t.slot_id in ids else -1
        n = len(slots)
        for k in range(1, n + 1):
            target = slots[(idx + step * k) % n]
            if swap or self._has_room(target):
                return self._move_to(handle, target, swap)
        return []

    def reorder(self, kind: SlotKind) -> list[Command]:
        """Réorganise une zone : compacte les tables dans l'ordre des slots."""
        tables = sorted((t for t in self.poker_tables() if self.kind_of(t.handle) == kind),
                        key=lambda t: (t.slot_id or 0, t.arrival))
        for t in tables:
            t.slot_id = None
        cmds: list[Command] = []
        for t in tables:
            slot = self.free_slot(kind) or self.least_loaded_slot(kind)
            if slot:
                cmds += self._place(t, slot)
        return cmds

    def reflow(self) -> list[Command]:
        """Replace toutes les fenêtres (changement de layout)."""
        windows = sorted(self.tables.values(), key=self._urgency_key)
        for t in windows:
            t.slot_id = None
            t.home_slot_id = None
        cmds: list[Command] = []
        for t in windows:
            waiting = t.needs_action
            t.needs_action = False
            if t.role == TABLE:
                slot = self._static_slot_for(t)
                if slot:
                    cmds += self._place(t, slot)
                if waiting:
                    cmds += self.set_action_required(t.handle, True, t.action_since or t.arrival)
            else:
                cmds += self.add_table(t)
        return cmds

    def set_layout(self, layout: Layout) -> list[Command]:
        self.layout = layout
        return self.reflow()

    def toggle_lock(self, handle) -> bool:
        t = self.tables.get(handle)
        if t is None:
            return False
        t.locked = not t.locked
        return t.locked

    def cycle(self, current, step: int) -> TableState | None:
        """Table suivante/précédente (Bring Next/Previous Table To Foreground)."""
        order = self.ordered_tables()
        if not order:
            return None
        handles = [t.handle for t in order]
        idx = handles.index(current) if current in handles else -1 if step > 0 else 0
        return order[(idx + step) % len(order)]

    def cycle_stack(self, slot_id: int) -> list[Command]:
        """Fait tourner la pile d'un slot (Cycle Hovered Stack)."""
        occ = [t for t in self.tables.values() if t.slot_id == slot_id]
        if len(occ) < 2:
            return []
        occ.sort(key=lambda t: t.arrival)
        first = occ[0]
        first.arrival = max(t.arrival for t in occ) + 1e-6
        return [Raise(first.handle)]
