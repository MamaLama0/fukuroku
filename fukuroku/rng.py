"""Générateur aléatoire pour mixer ses stratégies (Jurojin.Rng).

Tire un nombre uniforme dans [min, max] à intervalle régulier ; utilise le
générateur cryptographique du système (``secrets``).  Des seuils colorés
facilitent la lecture (ex. < 30 → rouge, < 70 → orange, sinon vert).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field


@dataclass
class RngSettings:
    minimum: int = 1
    maximum: int = 100
    interval_s: float = 5.0
    thresholds: list[tuple[int, str]] = field(default_factory=lambda: [(30, "#d9534f"), (70, "#f0ad4e"), (100, "#5cb85c")])
    font_size: int = 28
    opacity: float = 0.85
    position: tuple[int, int] | None = None
    roll_on: str = "time"  # "time" | "my_turn" (une table demande une action) | "hand"

    def to_dict(self) -> dict:
        return {"minimum": self.minimum, "maximum": self.maximum, "interval_s": self.interval_s, "roll_on": self.roll_on,
                "thresholds": [list(t) for t in self.thresholds], "font_size": self.font_size,
                "opacity": self.opacity, "position": list(self.position) if self.position else None}

    @classmethod
    def from_dict(cls, d: dict) -> "RngSettings":
        s = cls()
        s.minimum, s.maximum = int(d.get("minimum", 1)), int(d.get("maximum", 100))
        s.interval_s = float(d.get("interval_s", 5.0))
        if d.get("thresholds"):
            s.thresholds = [(int(a), str(b)) for a, b in d["thresholds"]]
        s.font_size = int(d.get("font_size", 28))
        s.opacity = float(d.get("opacity", 0.85))
        s.position = tuple(d["position"]) if d.get("position") else None
        s.roll_on = d.get("roll_on", "time")
        return s


def draw(minimum: int = 0, maximum: int = 99) -> int:
    if maximum < minimum:
        minimum, maximum = maximum, minimum
    return minimum + secrets.randbelow(maximum - minimum + 1)


def color_for(value: int, settings: RngSettings) -> str:
    span = max(1, settings.maximum - settings.minimum + 1)
    pct = (value - settings.minimum) * 100 / span
    for limit, color in sorted(settings.thresholds):
        if pct < limit:
            return color
    return settings.thresholds[-1][1] if settings.thresholds else "#ffffff"
