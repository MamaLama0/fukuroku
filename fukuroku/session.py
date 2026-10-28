"""Temps de session : minuteur, compteurs, notifications, historique.

Équivaut à SessionTimeWindow / SessionCountersService / HandsPlayedWindow et
à l'onglet « Sessions précédentes » ; tout reste en local (sessions.json et
journal CSV optionnel).
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SessionTracker:
    started_at: float | None = None  # None = minuteur pas encore démarré
    stopped_at: float | None = None
    tables_opened: int = 0
    max_simultaneous: int = 0
    current_tables: int = 0
    actions_required: int = 0
    hands_played: int = 0
    break_every_min: int = 0
    _last_break_reminder: float = field(default_factory=time.time)
    _hands_notified: bool = False
    _tables_notified: bool = False
    _all_closed_since: float | None = None

    # ------------------------------------------------------------------ minuteur
    @property
    def running(self) -> bool:
        return self.started_at is not None and self.stopped_at is None

    def start(self, now: float | None = None) -> None:
        if not self.running:
            self.started_at = now or time.time()
            self.stopped_at = None

    def stop(self, now: float | None = None) -> None:
        if self.running:
            self.stopped_at = now or time.time()

    def elapsed(self, now: float | None = None) -> float:
        if self.started_at is None:
            return 0.0
        end = self.stopped_at or now or time.time()
        return max(0.0, end - self.started_at)

    def format_elapsed(self, now: float | None = None) -> str:
        s = int(self.elapsed(now))
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"

    # ------------------------------------------------------------------ événements
    def on_table_opened(self, auto_start: bool = True, now: float | None = None) -> None:
        if auto_start:
            self.start(now)
        self.tables_opened += 1
        self.current_tables += 1
        self.max_simultaneous = max(self.max_simultaneous, self.current_tables)
        self._all_closed_since = None

    def on_table_closed(self, now: float | None = None) -> None:
        self.current_tables = max(0, self.current_tables - 1)
        if self.current_tables == 0:
            self._all_closed_since = now or time.time()

    def all_closed_for(self, now: float | None = None) -> float | None:
        """Depuis combien de secondes toutes les tables sont fermées (None si une table est ouverte)."""
        if self._all_closed_since is None:
            return None
        return (now or time.time()) - self._all_closed_since

    def on_action_required(self, auto_start: bool = False, now: float | None = None) -> None:
        if auto_start:
            self.start(now)
        self.actions_required += 1

    def on_hand(self) -> None:
        """Une main jouée (fournisseur de données, ou estimation : une action par main)."""
        self.hands_played += 1

    # ------------------------------------------------------------------ notifications
    def hands_goal_reached(self, goal: int) -> bool:
        if goal > 0 and not self._hands_notified and self.hands_played >= goal:
            self._hands_notified = True
            return True
        return False

    def tables_goal_reached(self, goal: int) -> bool:
        if goal > 0 and not self._tables_notified and self.tables_opened >= goal:
            self._tables_notified = True
            return True
        return False

    def break_due(self, now: float | None = None) -> bool:
        now = now or time.time()
        if self.break_every_min <= 0:
            return False
        if now - self._last_break_reminder >= self.break_every_min * 60:
            self._last_break_reminder = now
            return True
        return False

    def reset(self) -> None:
        self.__init__(break_every_min=self.break_every_min)

    # ------------------------------------------------------------------ sauvegarde
    def record(self) -> dict | None:
        if self.started_at is None:
            return None
        return {"date": time.strftime("%Y-%m-%d %H:%M", time.localtime(self.started_at)),
                "start": self.started_at, "duration_s": int(self.elapsed()), "tables": self.tables_opened,
                "max_tables": self.max_simultaneous, "hands": self.hands_played, "actions": self.actions_required}

    def append_to_log(self, path: Path) -> None:
        rec = self.record()
        if rec is None:
            return
        new = not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["debut", "duree_s", "tables_ouvertes", "max_simultanees", "mains", "actions"])
            w.writerow([rec["date"], rec["duration_s"], rec["tables"], rec["max_tables"], rec["hands"], rec["actions"]])


class SessionHistory:
    """Sessions précédentes (sessions.json)."""

    def __init__(self, path: Path):
        self.path = path
        self.sessions: list[dict] = []
        try:
            self.sessions = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.sessions = []

    def add(self, record: dict | None) -> None:
        if record and record.get("duration_s", 0) >= 60:
            self.sessions.append(record)
            self.save()

    def clear(self) -> None:
        self.sessions = []
        self.save()

    def filtered(self, start: float | None = None, end: float | None = None) -> list[dict]:
        return [s for s in self.sessions if (start is None or s["start"] >= start) and (end is None or s["start"] <= end)]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.sessions, indent=1), encoding="utf-8")
