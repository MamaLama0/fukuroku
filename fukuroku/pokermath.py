"""Calculs poker des overlays d'origine (Pot Odds, SPR, MDF, EFFS, OUTS, Bluff Equity).

Les valeurs d'entrée proviennent soit d'un fournisseur de données de table
(``TableDataProvider``), soit d'une saisie manuelle dans la calculatrice.
"""

from __future__ import annotations

from math import comb


def pot_odds(pot: float, to_call: float) -> float:
    """Équité minimale requise pour suivre : call / (pot + call). ``pot`` inclut la mise adverse."""
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def pot_odds_ratio(pot: float, to_call: float) -> float:
    """Cote « x contre 1 »."""
    return pot / to_call if to_call > 0 else float("inf")


def spr(effective_stack: float, pot: float) -> float:
    """Stack-to-Pot Ratio."""
    return effective_stack / pot if pot > 0 else float("inf")


def effective_stack(hero_stack: float, villain_stacks: list[float]) -> float:
    """Tapis effectif : min(héros, plus gros tapis adverse encore en jeu)."""
    if not villain_stacks:
        return hero_stack
    return min(hero_stack, max(villain_stacks))


def mdf(pot_before_bet: float, bet: float) -> float:
    """Minimum Defense Frequency = pot / (pot + mise)."""
    if bet <= 0:
        return 1.0
    return pot_before_bet / (pot_before_bet + bet)


def bluff_break_even(pot_before_bet: float, bet: float) -> float:
    """Fréquence de fold adverse nécessaire pour qu'un bluff soit rentable : mise / (pot + mise)."""
    if bet <= 0:
        return 0.0
    return bet / (pot_before_bet + bet)


def bluff_ratio(pot_before_bet: float, bet: float) -> float:
    """Part de bluffs dans une range de mise équilibrée (river) : mise / (pot + 2·mise)."""
    if bet <= 0:
        return 0.0
    return bet / (pot_before_bet + 2 * bet)


def outs_equity(outs: int, cards_to_come: int, unseen: int | None = None) -> float:
    """Probabilité exacte de toucher au moins un out.

    ``cards_to_come`` : 1 (turn→river ou flop→turn) ou 2 (flop→river).
    ``unseen`` : cartes inconnues (47 au flop, 46 au turn par défaut).
    """
    if outs <= 0 or cards_to_come <= 0:
        return 0.0
    if unseen is None:
        unseen = 47 if cards_to_come == 2 else 46
    outs = min(outs, unseen)
    miss = comb(unseen - outs, cards_to_come) / comb(unseen, cards_to_come)
    return 1.0 - miss


def outs_rule_of_2_and_4(outs: int, cards_to_come: int) -> float:
    """Approximation « règle de 2 et 4 »."""
    return min(1.0, outs * (4 if cards_to_come == 2 else 2) / 100)


def in_bb(amount: float, big_blind: float) -> float:
    """Conversion en grosses blindes (mode BB)."""
    return amount / big_blind if big_blind > 0 else 0.0


def format_bb(amount: float, big_blind: float) -> str:
    v = in_bb(amount, big_blind)
    return f"{v:.1f} BB" if v % 1 else f"{int(v)} BB"
