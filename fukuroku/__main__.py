"""Point d'entrée : ``python -m fukuroku`` ou ``fukuroku``."""

from __future__ import annotations

import argparse
import logging
import sys

from . import APP_NAME, __version__
from .backends import create_backend
from .config import Config, config_dir
from .geometry import Rect


def _demo_tables(backend) -> None:
    """Ajoute des tables simulées pour essayer l'interface sans client de poker."""
    titles = ["Halley - $0.25/$0.50 USD - No Limit Hold'em", "Ophelia - $0.25/$0.50 USD - No Limit Hold'em",
              "Zoom 77 - $0.50/$1 USD - NLHE", "Tournoi 31337 Table 4 - 100/200"]
    for i, title in enumerate(titles):
        backend.add_window(title, "PokerStars.exe", Rect(40 * i, 30 * i, 800, 550))
    backend.add_window("PokerStars Lobby", "PokerStars.exe", Rect(0, 0, 1000, 700))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fukuroku", description=f"{APP_NAME} — gestionnaire de tables de poker libre")
    parser.add_argument("--backend", choices=["auto", "windows", "linux", "macos", "simulation"], default="auto")
    parser.add_argument("--demo", action="store_true", help="backend simulé avec des tables factices")
    parser.add_argument("--config", help="fichier de configuration à utiliser")
    parser.add_argument("--list-windows", action="store_true", help="liste les fenêtres et la salle reconnue, puis quitte")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = parser.parse_args(argv)

    config_dir().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(config_dir() / "fukuroku.log",
                                                                               encoding="utf-8")])
    backend = create_backend("simulation" if args.demo else None if args.backend == "auto" else args.backend)
    if args.demo:
        _demo_tables(backend)

    from pathlib import Path
    config = Config.load(Path(args.config)) if args.config else Config.load()

    if args.list_windows:
        from .manager import TableManager
        mgr = TableManager(config, backend)
        for msg in backend.diagnostics():
            print(f"! {msg}")
        for w in backend.list_windows():
            site = mgr.identify(w)
            print(f"{'[' + site.name + ']' if site else '[—]':28} {w.process_name:24} {w.rect.to_list()} {w.title}")
        return 0

    from .ui.app import App
    App(config, backend).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
