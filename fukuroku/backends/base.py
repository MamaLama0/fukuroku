"""Interface commune des backends de plateforme (WinApiProvider multiplateforme)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Hashable

from ..geometry import Rect


@dataclass
class WindowInfo:
    handle: Hashable
    title: str
    process_name: str
    rect: Rect
    pid: int = 0
    class_name: str = ""
    minimized: bool = False


class BackendError(RuntimeError):
    pass


class Backend(ABC):
    name = "base"
    #: Fonctionnalités disponibles (affichées dans le tableau de bord).
    capabilities: set[str] = set()

    def diagnostics(self) -> list[str]:
        """Messages d'aide (dépendance manquante, permission requise…)."""
        return []

    @abstractmethod
    def list_windows(self) -> list[WindowInfo]: ...

    @abstractmethod
    def move_resize(self, handle, rect: Rect) -> None: ...

    @abstractmethod
    def bring_to_front(self, handle) -> None: ...

    def focus(self, handle) -> None:
        self.bring_to_front(handle)

    @abstractmethod
    def minimize(self, handle) -> None: ...

    @abstractmethod
    def close(self, handle) -> None: ...

    @abstractmethod
    def screens(self) -> list[Rect]: ...

    @abstractmethod
    def cursor_pos(self) -> tuple[int, int]: ...

    @abstractmethod
    def set_cursor_pos(self, x: int, y: int) -> None: ...

    @abstractmethod
    def click(self, x: int, y: int, button: str = "left", restore_cursor: bool = True) -> None: ...

    @abstractmethod
    def type_text(self, text: str) -> None: ...

    @abstractmethod
    def key_combo(self, combo: str) -> None:
        """Envoie une combinaison du type « ctrl+a » ou « enter »."""

    def pixel(self, x: int, y: int) -> tuple[int, int, int] | None:
        """Couleur d'un pixel écran (détection « action requise »)."""
        try:
            from PIL import ImageGrab  # optionnel
        except ImportError:
            return None
        try:
            img = ImageGrab.grab(bbox=(x, y, x + 1, y + 1), all_screens=True)
            return img.getpixel((0, 0))[:3]
        except Exception:
            return None

    def window_at(self, x: int, y: int, candidates: list[WindowInfo]) -> WindowInfo | None:
        """Fenêtre sous le point parmi ``candidates`` (ordre z : la première trouvée)."""
        return next((w for w in candidates if not w.minimized and w.rect.contains(x, y)), None)

    def foreground(self) -> Hashable | None:
        return None

    def set_title_bar(self, handle, visible: bool) -> None:
        """Masque/affiche la barre de titre d'une table (« Masquer la barre de titre des tables »)."""
