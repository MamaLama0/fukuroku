"""Raccourcis : actions, combinaisons clavier/souris/manette, collisions.

La liste des actions reprend l'énumération ``AppHotKeyName`` du logiciel
d'origine (Jurojin.HotKeys.dll), avec les mêmes identifiants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Action(str, Enum):
    SwitchLayout = "SwitchLayout"
    ReorderPlayingArea = "ReorderPlayingArea"
    ReorderObserverArea = "ReorderObserverArea"
    SendTableToPlayingArea = "SendTableToPlayingArea"
    SendTableToObserverArea = "SendTableToObserverArea"
    PeekActiveLayoutHotKey = "PeekActiveLayoutHotKey"
    RNGMoveToPointer = "RNGMoveToPointer"
    CycleHoveredStack = "CycleHoveredStack"
    Fold = "Fold"
    Check = "Check"
    BetRaise = "BetRaise"
    Button1 = "Button1"
    Button2 = "Button2"
    Button3 = "Button3"
    Button4 = "Button4"
    Button5 = "Button5"
    Button6 = "Button6"
    Button7 = "Button7"
    Button8 = "Button8"
    Button9 = "Button9"
    Button10 = "Button10"
    Button11 = "Button11"
    Button12 = "Button12"
    Button13 = "Button13"
    Button14 = "Button14"
    Button15 = "Button15"
    Button16 = "Button16"
    AllIn = "AllIn"
    DecreaseBet = "DecreaseBet"
    IncreaseBet = "IncreaseBet"
    Increment = "Increment"
    Decrement = "Decrement"
    BringNextTableToForeground = "BringNextTableToForeground"
    BringPreviousTableToForeground = "BringPreviousTableToForeground"
    MoveTableToNextSlot = "MoveTableToNextSlot"
    MoveTableToPreviousSlot = "MoveTableToPreviousSlot"
    MoveTableToNextSlotWithSwapping = "MoveTableToNextSlotWithSwapping"
    MoveTableToPreviousSlotWithSwapping = "MoveTableToPreviousSlotWithSwapping"
    FocusMostUrgentTable = "FocusMostUrgentTable"
    OpenMenu = "OpenMenu"
    DisableAllHotkeys = "DisableAllHotkeys"
    ToggleBBMode = "ToggleBBMode"
    ShowControllerCursor = "ShowControllerCursor"
    MinimizeTable = "MinimizeTable"
    CloseTable = "CloseTable"
    OpenNotificationsDebugWindow = "OpenNotificationsDebugWindow"
    SitoutNextHand = "SitoutNextHand"
    SitoutNextBB = "SitoutNextBB"
    SitBackIn = "SitBackIn"
    SitOutAtAllTables = "SitOutAtAllTables"
    SendTableToPlayingSlot = "SendTableToPlayingSlot"
    SendTableToObserverSlot = "SendTableToObserverSlot"
    SendTableToPlayingSlot1 = "SendTableToPlayingSlot1"
    SendTableToPlayingSlot2 = "SendTableToPlayingSlot2"
    SendTableToPlayingSlot3 = "SendTableToPlayingSlot3"
    SendTableToPlayingSlot4 = "SendTableToPlayingSlot4"
    SendTableToPlayingSlot5 = "SendTableToPlayingSlot5"
    SendTableToObserverSlot1 = "SendTableToObserverSlot1"
    SendTableToObserverSlot2 = "SendTableToObserverSlot2"
    SendTableToObserverSlot3 = "SendTableToObserverSlot3"
    SendTableToObserverSlot4 = "SendTableToObserverSlot4"
    SendTableToObserverSlot5 = "SendTableToObserverSlot5"
    HideShowBoard = "HideShowBoard"
    LockTableFromDynamicFlow = "LockTableFromDynamicFlow"
    ResetMainWindowPosition = "ResetMainWindowPosition"
    Ignore = "Ignore"


ACTION_LABELS_FR: dict[Action, str] = {
    Action.SwitchLayout: "Changer de layout",
    Action.ReorderPlayingArea: "Réorganiser la zone de jeu",
    Action.ReorderObserverArea: "Réorganiser la zone d'observation",
    Action.SendTableToPlayingArea: "Envoyer la table en zone de jeu",
    Action.SendTableToObserverArea: "Envoyer la table en zone d'observation",
    Action.PeekActiveLayoutHotKey: "Afficher le layout actif (maintenir)",
    Action.RNGMoveToPointer: "Déplacer le RNG sous le pointeur",
    Action.CycleHoveredStack: "Faire tourner la pile survolée",
    Action.Fold: "Se coucher (Fold)",
    Action.Check: "Check / Suivre",
    Action.BetRaise: "Miser / Relancer",
    Action.AllIn: "Tapis (All-in)",
    Action.DecreaseBet: "Diminuer la mise",
    Action.IncreaseBet: "Augmenter la mise",
    Action.Increment: "Incrément (+1 pas)",
    Action.Decrement: "Décrément (−1 pas)",
    Action.BringNextTableToForeground: "Table suivante au premier plan",
    Action.BringPreviousTableToForeground: "Table précédente au premier plan",
    Action.MoveTableToNextSlot: "Déplacer vers l'emplacement suivant",
    Action.MoveTableToPreviousSlot: "Déplacer vers l'emplacement précédent",
    Action.MoveTableToNextSlotWithSwapping: "Emplacement suivant (avec échange)",
    Action.MoveTableToPreviousSlotWithSwapping: "Emplacement précédent (avec échange)",
    Action.FocusMostUrgentTable: "Focus sur la table la plus urgente",
    Action.OpenMenu: "Ouvrir le menu",
    Action.DisableAllHotkeys: "Activer / désactiver tous les raccourcis",
    Action.ToggleBBMode: "Basculer l'affichage en BB",
    Action.ShowControllerCursor: "Afficher le curseur manette",
    Action.MinimizeTable: "Réduire la table",
    Action.CloseTable: "Fermer la table",
    Action.OpenNotificationsDebugWindow: "Journal des notifications",
    Action.SitoutNextHand: "Sit-out main suivante",
    Action.SitoutNextBB: "Sit-out prochaine BB",
    Action.SitBackIn: "Revenir à la table",
    Action.SitOutAtAllTables: "Sit-out sur toutes les tables",
    Action.SendTableToPlayingSlot: "Envoyer vers l'emplacement de jeu libre",
    Action.SendTableToObserverSlot: "Envoyer vers l'emplacement d'observation libre",
    Action.HideShowBoard: "Masquer / afficher le board",
    Action.LockTableFromDynamicFlow: "Verrouiller la table (hors flux dynamique)",
    Action.ResetMainWindowPosition: "Réinitialiser la position de la fenêtre principale",
    Action.Ignore: "Ignorer la table",
}
for _i in range(1, 17):
    ACTION_LABELS_FR[Action(f"Button{_i}")] = f"Bouton de mise {_i}"
for _i in range(1, 6):
    ACTION_LABELS_FR[Action(f"SendTableToPlayingSlot{_i}")] = f"Envoyer vers l'emplacement de jeu {_i}"
    ACTION_LABELS_FR[Action(f"SendTableToObserverSlot{_i}")] = f"Envoyer vers l'emplacement d'observation {_i}"

# Actions qui agissent sur une table (cible : survolée ou la plus urgente).
TABLE_ACTIONS = {
    Action.Fold, Action.Check, Action.BetRaise, Action.AllIn, Action.DecreaseBet, Action.IncreaseBet,
    Action.Increment, Action.Decrement, Action.SendTableToPlayingArea, Action.SendTableToObserverArea,
    Action.MoveTableToNextSlot, Action.MoveTableToPreviousSlot, Action.MoveTableToNextSlotWithSwapping,
    Action.MoveTableToPreviousSlotWithSwapping, Action.MinimizeTable, Action.CloseTable, Action.SitoutNextHand,
    Action.SitoutNextBB, Action.SitBackIn, Action.SendTableToPlayingSlot, Action.SendTableToObserverSlot,
    Action.LockTableFromDynamicFlow, Action.Ignore, Action.HideShowBoard,
    *(Action(f"Button{i}") for i in range(1, 17)),
    *(Action(f"SendTableToPlayingSlot{i}") for i in range(1, 6)),
    *(Action(f"SendTableToObserverSlot{i}") for i in range(1, 6)),
}

MODIFIERS = ("ctrl", "alt", "shift", "cmd")
_MOD_ALIASES = {"control": "ctrl", "ctl": "ctrl", "option": "alt", "opt": "alt", "win": "cmd", "super": "cmd",
                "meta": "cmd", "command": "cmd"}
MOUSE_INPUTS = {"mouse_left", "mouse_right", "mouse_middle", "mouse4", "mouse5", "wheel_up", "wheel_down"}
_KEY_ALIASES = {"esc": "escape", "return": "enter", "del": "delete", "ins": "insert", "pgup": "page_up",
                "pgdn": "page_down", "pageup": "page_up", "pagedown": "page_down", "spacebar": "space",
                "wheelup": "wheel_up", "wheeldown": "wheel_down", "xbutton1": "mouse4", "xbutton2": "mouse5",
                "lbutton": "mouse_left", "rbutton": "mouse_right", "mbutton": "mouse_middle"}

# Combinaisons réservées par le système (équivalent de RestrictedHotkeysValidator).
RESTRICTED = {
    frozenset({"ctrl", "alt"}) | {"delete"},
    frozenset({"alt"}) | {"tab"},
    frozenset({"alt"}) | {"f4"},
    frozenset({"cmd"}) | {"tab"},
    frozenset({"cmd"}) | {"q"},
    frozenset({"cmd"}) | {"space"},
    frozenset({"ctrl", "shift"}) | {"escape"},
}


@dataclass(frozen=True)
class HotKey:
    """Combinaison : modificateurs + touche principale (clavier ou souris)."""

    modifiers: frozenset[str]
    key: str

    @classmethod
    def parse(cls, text: str) -> "HotKey":
        parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
        if not parts:
            raise ValueError("raccourci vide")
        mods, key = set(), None
        for p in parts:
            p = _MOD_ALIASES.get(p, p)
            if p in MODIFIERS:
                mods.add(p)
            elif key is None:
                key = _KEY_ALIASES.get(p, p)
            else:
                raise ValueError(f"plusieurs touches principales dans « {text} »")
        if key is None:
            raise ValueError(f"aucune touche principale dans « {text} »")
        return cls(frozenset(mods), key)

    @property
    def is_mouse(self) -> bool:
        return self.key in MOUSE_INPUTS

    @property
    def is_restricted(self) -> bool:
        return frozenset(self.modifiers | {self.key}) in RESTRICTED

    def __str__(self) -> str:
        ordered = [m for m in MODIFIERS if m in self.modifiers]
        return "+".join(ordered + [self.key])


@dataclass
class Binding:
    action: Action
    hotkey: HotKey | None = None
    gamepad: str | None = None  # nom GamePadButtons
    enabled: bool = True


class HotKeyCollisionError(ValueError):
    pass


@dataclass
class HotKeyRegistry:
    bindings: dict[Action, Binding] = field(default_factory=dict)
    globally_enabled: bool = True

    def bind(self, action: Action, hotkey: HotKey | str | None) -> None:
        hk = HotKey.parse(hotkey) if isinstance(hotkey, str) else hotkey
        if hk is not None:
            if hk.is_restricted:
                raise HotKeyCollisionError(f"« {hk} » est réservé par le système")
            other = self.action_for(hk)
            if other is not None and other != action:
                raise HotKeyCollisionError(f"« {hk} » est déjà utilisé par {other.value}")
        b = self.bindings.setdefault(action, Binding(action))
        b.hotkey = hk

    def bind_gamepad(self, action: Action, button: str | None) -> None:
        if button:
            other = self.action_for_gamepad(button)
            if other is not None and other != action:
                raise HotKeyCollisionError(f"« {button} » est déjà utilisé par {other.value}")
        self.bindings.setdefault(action, Binding(action)).gamepad = button

    def unbind(self, action: Action) -> None:
        self.bindings.pop(action, None)

    def action_for(self, hk: HotKey) -> Action | None:
        return next((a for a, b in self.bindings.items() if b.hotkey == hk and b.enabled), None)

    def action_for_gamepad(self, button: str) -> Action | None:
        return next((a for a, b in self.bindings.items() if b.gamepad == button and b.enabled), None)

    def resolve(self, hk: HotKey) -> Action | None:
        """Action à déclencher ; seule DisableAllHotkeys reste active quand tout est désactivé."""
        action = self.action_for(hk)
        if not self.globally_enabled and action != Action.DisableAllHotkeys:
            return None
        return action

    def to_dict(self) -> dict:
        return {a.value: {"hotkey": str(b.hotkey) if b.hotkey else None, "gamepad": b.gamepad, "enabled": b.enabled}
                for a, b in self.bindings.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "HotKeyRegistry":
        reg = cls()
        for name, v in d.items():
            try:
                action = Action(name)
            except ValueError:
                continue
            hk = HotKey.parse(v["hotkey"]) if v.get("hotkey") else None
            reg.bindings[action] = Binding(action, hk, v.get("gamepad"), v.get("enabled", True))
        return reg


def default_registry() -> HotKeyRegistry:
    reg = HotKeyRegistry()
    defaults = {
        Action.Fold: "f1", Action.Check: "f2", Action.BetRaise: "f3", Action.AllIn: "ctrl+f3",
        Action.IncreaseBet: "wheel_up", Action.DecreaseBet: "wheel_down",
        Action.BringNextTableToForeground: "ctrl+tab", Action.BringPreviousTableToForeground: "ctrl+shift+tab",
        Action.FocusMostUrgentTable: "f4", Action.SwitchLayout: "ctrl+alt+l",
        Action.SendTableToPlayingArea: "ctrl+up", Action.SendTableToObserverArea: "ctrl+down",
        Action.MoveTableToNextSlot: "ctrl+right", Action.MoveTableToPreviousSlot: "ctrl+left",
        Action.LockTableFromDynamicFlow: "ctrl+alt+k", Action.DisableAllHotkeys: "ctrl+alt+h",
        Action.RNGMoveToPointer: "ctrl+alt+r", Action.CycleHoveredStack: "mouse_middle",
        Action.ReorderPlayingArea: "ctrl+alt+o",
    }
    for action, text in defaults.items():
        reg.bind(action, text)
    gamepad = {Action.Fold: "X", Action.Check: "A", Action.BetRaise: "Y", Action.FocusMostUrgentTable: "B",
               Action.IncreaseBet: "DPadUp", Action.DecreaseBet: "DPadDown",
               Action.BringNextTableToForeground: "RightButton", Action.BringPreviousTableToForeground: "LeftButton",
               Action.ShowControllerCursor: "Select", Action.OpenMenu: "Start"}
    for action, button in gamepad.items():
        reg.bind_gamepad(action, button)
    return reg
