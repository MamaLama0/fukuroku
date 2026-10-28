"""Primitives géométriques indépendantes de la plateforme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom

    def intersection(self, other: "Rect") -> "Rect | None":
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2, y2 = min(self.right, other.right), min(self.bottom, other.bottom)
        if x2 <= x1 or y2 <= y1:
            return None
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def overlap_ratio(self, other: "Rect") -> float:
        inter = self.intersection(other)
        if inter is None or self.area == 0:
            return 0.0
        return inter.area / self.area

    def distance_to(self, other: "Rect") -> float:
        (ax, ay), (bx, by) = self.center, other.center
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def fit_aspect(self, aspect: float | None) -> "Rect":
        """Plus grand rectangle de ratio ``aspect`` (largeur/hauteur) centré dans self."""
        if not aspect or self.w <= 0 or self.h <= 0:
            return self
        if self.w / self.h > aspect:
            w = round(self.h * aspect)
            return Rect(self.x + (self.w - w) // 2, self.y, w, self.h)
        h = round(self.w / aspect)
        return Rect(self.x, self.y + (self.h - h) // 2, self.w, h)

    def relative_point(self, fx: float, fy: float) -> tuple[int, int]:
        """Point absolu à partir de fractions (0..1) de la largeur/hauteur."""
        return (round(self.x + fx * self.w), round(self.y + fy * self.h))

    def to_fraction(self, px: float, py: float) -> tuple[float, float]:
        return ((px - self.x) / self.w if self.w else 0.0, (py - self.y) / self.h if self.h else 0.0)

    def scaled(self, factor: float) -> "Rect":
        return Rect(round(self.x * factor), round(self.y * factor), round(self.w * factor), round(self.h * factor))

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]

    @classmethod
    def from_list(cls, values) -> "Rect":
        x, y, w, h = (int(v) for v in values)
        return cls(x, y, w, h)
