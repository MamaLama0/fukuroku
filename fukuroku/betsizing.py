"""Boutons de mise (Bet Buttons) au format du logiciel d'origine.

Chaque bouton (1 à 16) porte trois valeurs, comme dans l'onglet « Boutons de
mise » d'origine :

* mise préflop en grosses blindes (« Big Blind ou Button Blind ») ;
* mise normale en % du pot (postflop) ;
* multiplicateur de la mise précédente (« X fois la mise/relance précédente »).

Le « mode de relance » choisit la valeur utilisée face à une mise : BB, PSB %
(pot-size bet) ou multiplicateur.  Un bouton peut aussi être une mise
géométrique (tapis en 2 ou 3 streets).

Les tailles en BB ne demandent que les blindes (lues dans le titre de la
table) ; les tailles liées au pot nécessitent un fournisseur de données.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass
class BetButton:
    preflop_bb: float | None = None
    postflop_pct: float | None = None  # en % du pot (33 = 33 %)
    multiplier: float | None = None
    geometric: bool = False

    @property
    def label(self) -> str:
        parts = []
        if self.preflop_bb:
            parts.append(f"{self.preflop_bb:g}bb")
        if self.geometric:
            parts.append("geo")
        elif self.postflop_pct:
            parts.append(f"{self.postflop_pct:g}%")
        if self.multiplier:
            parts.append(f"{self.multiplier:g}x")
        return " / ".join(parts) or "—"

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "BetButton":
        if "mode" in d:  # configuration 1.0 (BetSize)
            v = float(d["value"])
            return cls(preflop_bb=v if d["mode"] == "bb" else None,
                       postflop_pct=v * 100 if d["mode"] == "pot" else None)
        f = lambda k: float(d[k]) if d.get(k) not in (None, "") else None
        return cls(f("preflop_bb"), f("postflop_pct"), f("multiplier"), bool(d.get("geometric", False)))


DEFAULT_BET_BUTTONS = [
    BetButton(2.0, 33, 2.5), BetButton(2.5, 50, 3.0), BetButton(3.0, 75, 3.5), BetButton(3.5, 100, 4.0),
    BetButton(4.0, 25, 2.2), BetButton(5.0, 66, 3.0), BetButton(10.0, 125, 4.5), BetButton(None, 150, 5.0),
]


@dataclass
class RaiseMode:
    """Comportement face à une mise (« Mode de relance »)."""

    preflop: str = "bb"  # "bb" | "psb" | "times"
    postflop: str = "psb"  # "psb" | "times"

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "RaiseMode":
        return cls(d.get("preflop", "bb"), d.get("postflop", "psb"))


@dataclass
class BetContext:
    big_blind: float | None
    street: str = "preflop"  # preflop | flop | turn | river
    pot: float | None = None  # pot avant la mise à suivre
    to_call: float = 0.0
    last_bet: float | None = None  # dernière mise/relance adverse
    stack: float | None = None


def round_to_step(amount: float, step: float) -> float:
    if step <= 0:
        return amount
    q = (Decimal(str(amount)) / Decimal(str(step))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return float(q * Decimal(str(step)))


def geometric_fraction(stack: float, pot: float, streets: int) -> float:
    """Fraction du pot à miser à chaque street pour être à tapis en ``streets`` mises."""
    if pot <= 0 or streets <= 0:
        return 0.0
    return ((1 + 2 * stack / pot) ** (1 / streets) - 1) / 2


def psb(pct: float, pot: float, to_call: float) -> float:
    """Mise/relance au pourcentage du pot (la relance inclut le call)."""
    return to_call + pct / 100 * (pot + 2 * to_call) if to_call else pct / 100 * pot


def compute_bet(button: BetButton, ctx: BetContext, mode: RaiseMode | None = None,
                geometric_streets: int | None = None) -> float | None:
    """Montant total à saisir dans le champ de mise ; ``None`` si les données manquent."""
    mode = mode or RaiseMode()
    bb = ctx.big_blind
    if ctx.street == "preflop":  # face à une relance : la dernière mise dépasse la grosse blinde
        facing = bool(bb and (ctx.last_bet or 0) > bb + 1e-9)
    else:
        facing = ctx.to_call > 0
    amount: float | None = None
    if ctx.street == "preflop":
        choice = mode.preflop if facing else "bb"
        if choice == "times" and button.multiplier and ctx.last_bet:
            amount = button.multiplier * ctx.last_bet
        elif choice == "psb" and button.postflop_pct and ctx.pot is not None:
            amount = psb(button.postflop_pct, ctx.pot, ctx.to_call)
        if amount is None and button.preflop_bb and bb:
            amount = button.preflop_bb * bb
    else:
        if button.geometric and ctx.pot and ctx.stack:
            streets = geometric_streets or {"flop": 3, "turn": 2}.get(ctx.street, 1)
            amount = ctx.to_call + geometric_fraction(ctx.stack, ctx.pot + 2 * ctx.to_call, streets) * (ctx.pot + 2 * ctx.to_call)
        elif facing and mode.postflop == "times" and button.multiplier and ctx.last_bet:
            amount = button.multiplier * ctx.last_bet
        elif button.postflop_pct and ctx.pot is not None:
            amount = psb(button.postflop_pct, ctx.pot, ctx.to_call)
        elif button.preflop_bb and bb and ctx.pot is None:
            amount = button.preflop_bb * bb  # pas de données : repli sur la taille en BB
    if amount is None:
        return None
    step = bb / 100 if bb else 0.01
    amount = round_to_step(amount, step)
    if ctx.stack is not None:
        amount = min(amount, ctx.stack)
    return amount


def adjust_bet(current: float, direction: int, big_blind: float | None, step_bb: float = 0.5) -> float:
    """Augmente/diminue la mise d'un pas (Increment / Decrement, molette)."""
    step = (big_blind or 1.0) * step_bb
    return max(0.0, round_to_step(current + direction * step, (big_blind or 1.0) / 100))


def format_amount(amount: float, decimal_comma: bool = False) -> str:
    """Formatage pour saisie dans le champ de mise du client."""
    text = f"{amount:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if decimal_comma else text
