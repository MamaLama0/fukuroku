"""Définitions des salles de poker prises en charge.

Le logiciel d'origine embarque un module par salle (Jurojin.Core.<Salle>.dll)
dont les motifs de reconnaissance sont chiffrés.  Ici, tout est déclaratif et
modifiable par l'utilisateur dans l'onglet « Salles » : noms de processus,
expressions régulières de titres de fenêtres, classes de fenêtres (Windows),
ratio des tables et points de clic calibrables (fractions de la table).

Les valeurs par défaut sont des points de départ raisonnables : la
calibration (« Calibrer les clics ») les ajuste à votre client et à votre skin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Points de clic par défaut (fraction largeur, fraction hauteur) — client « standard ».
DEFAULT_CLICK_POINTS: dict[str, tuple[float, float]] = {
    "fold": (0.62, 0.92),
    "check": (0.75, 0.92),
    "bet": (0.89, 0.92),
    "bet_box": (0.90, 0.83),
    "button1": (0.62, 0.78), "button2": (0.68, 0.78), "button3": (0.74, 0.78), "button4": (0.80, 0.78),
    "button5": (0.86, 0.78), "button6": (0.92, 0.78), "button7": (0.62, 0.74), "button8": (0.68, 0.74),
    "button9": (0.74, 0.74), "button10": (0.80, 0.74), "button11": (0.86, 0.74), "button12": (0.92, 0.74),
    "button13": (0.62, 0.70), "button14": (0.68, 0.70), "button15": (0.74, 0.70), "button16": (0.80, 0.70),
    "allin": (0.95, 0.78),
    "sitout_next_hand": (0.03, 0.93),
    "sitout_next_bb": (0.03, 0.96),
    "sit_back_in": (0.50, 0.60),
    "increase_bet": (0.97, 0.83),
    "decrease_bet": (0.80, 0.83),
}


@dataclass
class PixelProbe:
    """Détection « action requise » par échantillonnage d'un pixel de la table.

    Quand la couleur au point (fx, fy) est proche de ``color`` (tolérance
    euclidienne en RGB), la table attend une action du joueur.
    """

    fx: float = 0.62
    fy: float = 0.92
    color: tuple[int, int, int] = (180, 30, 30)
    tolerance: int = 60
    enabled: bool = False

    def matches(self, rgb: tuple[int, int, int] | None) -> bool:
        if rgb is None:
            return False
        dist = sum((a - b) ** 2 for a, b in zip(rgb, self.color)) ** 0.5
        return dist <= self.tolerance

    def to_dict(self) -> dict:
        return {"fx": self.fx, "fy": self.fy, "color": list(self.color), "tolerance": self.tolerance, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, d: dict) -> "PixelProbe":
        return cls(d.get("fx", 0.62), d.get("fy", 0.92), tuple(d.get("color", (180, 30, 30))),
                   d.get("tolerance", 60), d.get("enabled", False))


@dataclass
class SiteDefinition:
    id: str
    name: str
    processes: list[str] = field(default_factory=list)
    table_title: str = ""
    lobby_title: str = ""
    exclude_title: str = ""
    window_classes: list[str] = field(default_factory=list)
    table_aspect: float = 1.4545
    min_table_width: int = 300
    enabled: bool = True
    click_points: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_CLICK_POINTS))
    probe: PixelProbe = field(default_factory=PixelProbe)
    # Raccourci de sélection du champ de mise avant saisie (« ctrl+a » / « cmd+a »).
    select_all_keys: str = ""
    replay_title: str = ""
    # Onglet « Positionnement des tables » de l'original.
    tiling: bool = True
    new_table: str = "playing"  # "playing" | "observer" | "nothing"
    in_hand_trigger: str = "first_action"  # "new_hand" | "vpip" | "first_action"
    # Onglet « Contournement des hotkeys » : raccourcis configurés dans le client
    # (action → touche) ; s'ils sont renseignés, Fukuroku envoie la touche au lieu de cliquer.
    site_keys: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self._table_re = re.compile(self.table_title, re.I) if self.table_title else None
        self._lobby_re = re.compile(self.lobby_title, re.I) if self.lobby_title else None
        self._exclude_re = re.compile(self.exclude_title, re.I) if self.exclude_title else None
        self._replay_re = re.compile(self.replay_title, re.I) if self.replay_title else None

    def matches_process(self, process_name: str) -> bool:
        if not self.processes:
            return True
        name = _normalize_process(process_name)
        return any(_normalize_process(p) == name for p in self.processes)

    def is_lobby(self, title: str) -> bool:
        return bool(self._lobby_re and self._lobby_re.search(title))

    def is_replay(self, title: str) -> bool:
        return bool(self._replay_re and self._replay_re.search(title))

    def is_table(self, title: str, class_name: str = "", width: int = 0, height: int = 0) -> bool:
        if not title or self.is_lobby(title) or self.is_replay(title):
            return False
        if self._exclude_re and self._exclude_re.search(title):
            return False
        if width and width < self.min_table_width:
            return False
        if self.window_classes and class_name and class_name in self.window_classes:
            return True
        if self._table_re:
            return bool(self._table_re.search(title))
        if width and height:  # Heuristique : fenêtre au format table.
            return 1.15 <= width / height <= 1.9
        return False

    def click_point(self, name: str) -> tuple[float, float] | None:
        return self.click_points.get(name) or DEFAULT_CLICK_POINTS.get(name)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "processes": self.processes, "table_title": self.table_title,
            "lobby_title": self.lobby_title, "exclude_title": self.exclude_title,
            "window_classes": self.window_classes, "table_aspect": self.table_aspect,
            "min_table_width": self.min_table_width, "enabled": self.enabled,
            "click_points": {k: list(v) for k, v in self.click_points.items()},
            "probe": self.probe.to_dict(), "select_all_keys": self.select_all_keys,
            "replay_title": self.replay_title, "tiling": self.tiling, "new_table": self.new_table,
            "in_hand_trigger": self.in_hand_trigger, "site_keys": dict(self.site_keys),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SiteDefinition":
        points = dict(DEFAULT_CLICK_POINTS)
        points.update({k: tuple(v) for k, v in d.get("click_points", {}).items()})
        return cls(
            d["id"], d.get("name", d["id"]), list(d.get("processes", [])), d.get("table_title", ""),
            d.get("lobby_title", ""), d.get("exclude_title", ""), list(d.get("window_classes", [])),
            float(d.get("table_aspect", 1.4545)), int(d.get("min_table_width", 300)), bool(d.get("enabled", True)),
            points, PixelProbe.from_dict(d.get("probe", {})), d.get("select_all_keys", ""),
            d.get("replay_title", ""), bool(d.get("tiling", True)), d.get("new_table", "playing"),
            d.get("in_hand_trigger", "first_action"), dict(d.get("site_keys", {})),
        )


def _normalize_process(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".exe", ".app", ".bin"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    return name


# Motif de mise générique : « $0.25/$0.50 », « €1/€2 », « 0,02/0,05 », « 100/200 ».
_STAKES = r"[\$€£₹]?\s?\d+(?:[.,]\d+)?[kK]?\s?/\s?[\$€£₹]?\s?\d+(?:[.,]\d+)?[kK]?"

# Salles reconnues par le logiciel d'origine (une DLL Core.<Salle> chacune).
DEFAULT_SITES: list[SiteDefinition] = [
    SiteDefinition("pokerstars", "PokerStars", ["PokerStars", "PokerStars.exe", "PokerStarsUK", "PokerStars.FR"],
                   table_title=rf"{_STAKES}|Tournament \d+|Tournoi \d+|Table \d+", lobby_title=r"Lobby|Lobby PokerStars",
                   window_classes=["PokerStarsTableFrameClass"], replay_title=r"Replayer|Hand Replay"),
    SiteDefinition("ggnet", "GGPoker / GGNetwork", ["GGnet", "GGPoker", "GGPCOM", "GGPoker.exe"],
                   table_title=rf"{_STAKES}|Hold'?em|Omaha|Rush|Spin", lobby_title=r"^GG(Poker|net)?$|Lobby",
                   replay_title=r"Replay|Hand History"),
    SiteDefinition("winamax", "Winamax", ["Winamax", "Winamax Poker"],
                   table_title=rf"{_STAKES}|Expresso|Holdem|Hold'em|Omaha|\(\d+\)", lobby_title=r"^Winamax", replay_title=r"Replayer|Historique"),
    SiteDefinition("pacific", "888poker / Pacific", ["poker", "888poker", "PacificPoker"],
                   table_title=rf"{_STAKES}|Snap|BLAST|Hold'?em", lobby_title=r"888poker$|Lobby"),
    SiteDefinition("partypoker", "partypoker", ["PartyGaming", "partypoker"],
                   table_title=rf"{_STAKES}|fastforward|SPINS|Hold'?em", lobby_title=r"^partypoker|Lobby"),
    SiteDefinition("ipoker", "iPoker", ["casino", "iPoker", "PokerClient"],
                   table_title=rf"{_STAKES}|Hold'?em|Omaha", lobby_title=r"Lobby|Poker$"),
    SiteDefinition("wptglobal", "WPT Global", ["WPT Global", "WPTGlobal"],
                   table_title=rf"{_STAKES}|Hold'?em|Omaha", lobby_title=r"^WPT Global$"),
    SiteDefinition("wptgold", "WPT Gold", ["WPT Gold", "WPTGold"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("clubgg", "ClubGG", ["ClubGG"], table_title=rf"{_STAKES}|Hold'?em|PLO", lobby_title=r"^ClubGG$"),
    SiteDefinition("coinpoker", "CoinPoker", ["CoinPoker"], table_title=rf"{_STAKES}|Hold'?em|PLO", lobby_title=r"^CoinPoker$"),
    SiteDefinition("winningpoker", "Winning Poker Network", ["AmericasCardroom", "BlackChipPoker", "WPN"],
                   table_title=rf"{_STAKES}|Hold'?em|Omaha", lobby_title=r"Lobby"),
    SiteDefinition("bodog", "Bodog / Ignition", ["Bodog", "Ignition", "Bovada"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("chico", "Chico Poker", ["TigerGaming", "SportsBetting", "BetOnline"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("kkpoker", "KKPoker", ["KKPoker"], table_title=_STAKES, lobby_title=r"^KKPoker$"),
    SiteDefinition("pppoker", "PPPoker", ["PPPoker"], table_title=_STAKES, lobby_title=r"^PPPoker$"),
    SiteDefinition("qqpk", "QQPK", ["QQPK"], table_title=_STAKES, lobby_title=r"^QQPK$"),
    SiteDefinition("unibet", "Unibet", ["Unibet", "UnibetPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("betclic", "Betclic", ["Betclic", "BetclicPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("phenom", "Phenom Poker", ["PhenomPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("pokerbaazi", "PokerBaazi", ["PokerBaazi"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("adda52", "Adda52", ["Adda52"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("skypoker", "Sky Poker", ["SkyPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("rio", "Rio Poker", ["RioPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("vang", "VangPoker", ["VangPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("fourpoker", "4Poker", ["4Poker", "FourPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("poeples", "People's Poker", ["PeoplesPoker"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("pokerdom", "Pokerdom", ["Pokerdom"], table_title=_STAKES, lobby_title=r"Lobby"),
    SiteDefinition("generic", "Générique (toute fenêtre au format table)", [], enabled=False),
]


def default_sites() -> list[SiteDefinition]:
    return [SiteDefinition.from_dict(s.to_dict()) for s in DEFAULT_SITES]


_STAKE_PAIR = re.compile(
    r"(?P<cur>[\$€£₹])?\s?(?P<sb>\d+(?:[.,]\d+)?)(?P<sbk>[kK])?\s?/\s?[\$€£₹]?\s?(?P<bb>\d+(?:[.,]\d+)?)(?P<bbk>[kK])?"
)
_NL_LEVEL = re.compile(r"\b(?:NL|PL|FL|NLH|PLO)(?P<level>\d+)\b", re.I)


@dataclass(frozen=True)
class Stakes:
    small_blind: float
    big_blind: float
    currency: str = ""


def parse_stakes(title: str) -> Stakes | None:
    """Extrait les blindes d'un titre de table (équivalent de ITableStakeParser)."""
    m = _STAKE_PAIR.search(title or "")
    if m:
        sb = float(m["sb"].replace(",", ".")) * (1000 if m["sbk"] else 1)
        bb = float(m["bb"].replace(",", ".")) * (1000 if m["bbk"] else 1)
        if 0 < sb <= bb:
            return Stakes(sb, bb, m["cur"] or "")
    m = _NL_LEVEL.search(title or "")
    if m:  # NL50 = blindes 0.25/0.50 (100 BB de cave max)
        bb = int(m["level"]) / 100
        return Stakes(bb / 2, bb)
    return None


class StakeTier:
    """Paliers de limites (équivalent de TableStakeTier)."""

    MICRO, LOW, MID, HIGH = "micro", "low", "mid", "high"

    @staticmethod
    def classify(stakes: Stakes | None) -> str | None:
        if stakes is None:
            return None
        bb = stakes.big_blind
        if bb <= 0.10:
            return StakeTier.MICRO
        if bb <= 0.50:
            return StakeTier.LOW
        if bb <= 4:
            return StakeTier.MID
        return StakeTier.HIGH
