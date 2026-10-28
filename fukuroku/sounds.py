"""Alertes sonores (AudioPlaybackService) avec les sons d'origine.

Sons disponibles : Alien, Angels, Ascending, Bell, Bird, Bubble, Galactic,
Pong, Salty, Shimmer, Weirdy (WAV 16 bits stéréo).  Un fichier WAV
quelconque peut aussi être choisi.  Le volume est appliqué en générant une
copie atténuée (mise en cache), ce qui fonctionne sur les trois systèmes.
"""

from __future__ import annotations

import array
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

from . import assets

DEFAULT_SOUND = "Bell"
_cache_dir = Path(tempfile.gettempdir()) / "fukuroku-sounds"


def available() -> dict[str, Path]:
    return assets.sounds()


def resolve(name_or_path: str | Path | None) -> Path | None:
    if not name_or_path:
        return None
    builtin = available().get(str(name_or_path))
    if builtin:
        return builtin
    p = Path(name_or_path)
    return p if p.exists() else available().get(DEFAULT_SOUND)


def with_volume(path: Path, volume: float) -> Path:
    """Copie du WAV au volume demandé (0..1) ; 16 bits uniquement, sinon fichier d'origine."""
    volume = max(0.0, min(1.0, volume))
    if volume >= 0.999:
        return path
    out = _cache_dir / f"{path.stem}-{int(volume * 100)}.wav"
    if out.exists():
        return out
    try:
        with wave.open(str(path), "rb") as r:
            params = r.getparams()
            if params.sampwidth != 2:
                return path
            samples = array.array("h", r.readframes(params.nframes))
        if sys.byteorder == "big":
            samples.byteswap()
        samples = array.array("h", (int(s * volume) for s in samples))
        if sys.byteorder == "big":
            samples.byteswap()
        out.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out), "wb") as w:
            w.setparams(params)
            w.writeframes(samples.tobytes())
        return out
    except (OSError, wave.Error, EOFError):
        return path


def _player_command(path: Path) -> list[str] | None:
    if sys.platform == "darwin":
        return ["afplay", str(path)]
    for cmd in (["paplay"], ["pw-play"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd + [str(path)]
    return None


def play(sound: str | Path | None, volume: float = 1.0) -> None:
    """Lecture non bloquante d'un son d'origine (par nom) ou d'un fichier WAV."""
    path = resolve(sound)
    if path is None:
        return
    path = with_volume(path, volume)
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return
    cmd = _player_command(path)
    if cmd:
        threading.Thread(target=lambda: subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
                         daemon=True).start()
