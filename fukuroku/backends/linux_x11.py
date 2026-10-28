"""Backend Linux (X11 / XWayland) basé sur wmctrl, xdotool et xrandr.

Les clients de poker Windows tournent sous Wine/Proton et sont donc des
fenêtres X11 (y compris dans une session Wayland via XWayland).  Sous Wayland,
le compositeur peut refuser le déplacement des fenêtres X11 : KDE Plasma et la
plupart des gestionnaires X11 l'autorisent, GNOME/Mutter parfois non.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from ..geometry import Rect
from .base import Backend, BackendError, WindowInfo

XDOTOOL_KEYS = {"enter": "Return", "escape": "Escape", "tab": "Tab", "space": "space", "backspace": "BackSpace",
                "delete": "Delete", "insert": "Insert", "home": "Home", "end": "End", "page_up": "Prior",
                "page_down": "Next", "left": "Left", "right": "Right", "up": "Up", "down": "Down",
                "cmd": "super", "ctrl": "ctrl", "alt": "alt", "shift": "shift"}
BUTTONS = {"left": "1", "middle": "2", "right": "3"}

_WMCTRL_LINE = re.compile(
    r"^(?P<id>0x[0-9a-fA-F]+)\s+(?P<desk>-?\d+)\s+(?P<pid>\d+)\s+(?P<x>-?\d+)\s+(?P<y>-?\d+)\s+(?P<w>\d+)\s+(?P<h>\d+)"
    r"\s+(?P<cls>\S+)\s+(?P<host>\S+)\s?(?P<title>.*)$")
_XRANDR = re.compile(r" connected (?:primary )?(?P<w>\d+)x(?P<h>\d+)\+(?P<x>\d+)\+(?P<y>\d+)")


def parse_wmctrl(output: str) -> list[dict]:
    rows = []
    for line in output.splitlines():
        m = _WMCTRL_LINE.match(line)
        if m:
            rows.append(m.groupdict())
    return rows


def parse_xrandr(output: str) -> list[Rect]:
    return [Rect(int(m["x"]), int(m["y"]), int(m["w"]), int(m["h"])) for m in _XRANDR.finditer(output)]


def process_name(pid: int) -> str:
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[0].decode(errors="ignore")
        name = cmd.replace("\\", "/").rsplit("/", 1)[-1]
        if name and not name.startswith("wine"):
            return name
        return Path(f"/proc/{pid}/comm").read_text().strip()
    except OSError:
        return ""


class LinuxX11Backend(Backend):
    name = "Linux (X11 / XWayland)"
    capabilities = {"windows", "move", "click", "keys", "screens"}

    def __init__(self):
        self.wmctrl = shutil.which("wmctrl")
        self.xdotool = shutil.which("xdotool")
        self.xrandr = shutil.which("xrandr")

    def diagnostics(self):
        msgs = []
        if not os.environ.get("DISPLAY"):
            msgs.append("Aucun DISPLAY X11 : lancez les clients de poker via XWayland/Wine et exportez DISPLAY.")
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            msgs.append("Session Wayland : seules les fenêtres XWayland (Wine/Proton) peuvent être placées ; "
                        "sous GNOME le déplacement peut être refusé par le compositeur.")
        for tool, path in (("wmctrl", self.wmctrl), ("xdotool", self.xdotool), ("xrandr", self.xrandr)):
            if not path:
                msgs.append(f"Outil manquant : {tool} (installez-le via votre gestionnaire de paquets).")
        try:
            import PIL  # noqa: F401
        except ImportError:
            msgs.append("Pillow absent : la détection d'action par pixel est désactivée (pip install pillow).")
        return msgs

    def _run(self, *args: str, check: bool = False) -> str:
        if not args[0]:
            raise BackendError("outil système manquant (wmctrl/xdotool/xrandr)")
        res = subprocess.run(args, capture_output=True, text=True, timeout=5)
        if check and res.returncode != 0:
            raise BackendError(res.stderr.strip() or f"échec : {' '.join(args)}")
        return res.stdout

    # ------------------------------------------------------------------ fenêtres
    def list_windows(self):
        if not self.wmctrl:
            return []
        out = []
        for row in parse_wmctrl(self._run(self.wmctrl, "-lpGx")):
            if row["desk"] == "-1":  # panneaux, docks
                continue
            pid = int(row["pid"])
            out.append(WindowInfo(int(row["id"], 16), row["title"], process_name(pid),
                                  Rect(int(row["x"]), int(row["y"]), int(row["w"]), int(row["h"])), pid, row["cls"]))
        # wmctrl liste dans l'ordre de création ; xdotool fournit l'ordre z si disponible.
        if self.xdotool:
            order = self._stacking_order()
            if order:
                rank = {wid: i for i, wid in enumerate(order)}
                out.sort(key=lambda w: rank.get(w.handle, len(rank)))
        return out

    def _stacking_order(self) -> list[int]:
        try:
            raw = subprocess.run(["xprop", "-root", "_NET_CLIENT_LIST_STACKING"], capture_output=True, text=True,
                                 timeout=3).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        ids = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", raw)]
        return list(reversed(ids))  # du dessus vers le dessous

    def move_resize(self, handle, rect):
        wid = hex(handle)
        self._run(self.wmctrl, "-i", "-r", wid, "-b", "remove,maximized_vert,maximized_horz")
        self._run(self.wmctrl, "-i", "-r", wid, "-e", f"0,{rect.x},{rect.y},{rect.w},{rect.h}")

    def bring_to_front(self, handle):
        if self.xdotool:
            self._run(self.xdotool, "windowraise", str(handle))
        else:
            self.focus(handle)

    def focus(self, handle):
        self._run(self.wmctrl, "-i", "-a", hex(handle))

    def minimize(self, handle):
        self._run(self.xdotool, "windowminimize", str(handle))

    def set_title_bar(self, handle, visible):
        hints = "2, 0, 1, 0, 0" if visible else "2, 0, 0, 0, 0"
        self._run("xprop", "-id", hex(handle), "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", hints)

    def close(self, handle):
        self._run(self.wmctrl, "-i", "-c", hex(handle))

    def foreground(self):
        if not self.xdotool:
            return None
        out = self._run(self.xdotool, "getactivewindow").strip()
        return int(out) if out.isdigit() else None

    def screens(self):
        if self.xrandr:
            rects = parse_xrandr(self._run(self.xrandr, "--query"))
            if rects:
                return sorted(rects, key=lambda r: (r.x, r.y))
        return [Rect(0, 0, 1920, 1080)]

    # ------------------------------------------------------------------ entrées
    def cursor_pos(self):
        out = self._run(self.xdotool, "getmouselocation", "--shell")
        vals = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        return (int(vals.get("X", 0)), int(vals.get("Y", 0)))

    def set_cursor_pos(self, x, y):
        self._run(self.xdotool, "mousemove", str(int(x)), str(int(y)))

    def click(self, x, y, button="left", restore_cursor=True):
        args = [self.xdotool, "mousemove", "--sync", str(int(x)), str(int(y)), "click", BUTTONS.get(button, "1")]
        if restore_cursor:
            args += ["mousemove", "restore"]
        self._run(*args)

    def type_text(self, text):
        self._run(self.xdotool, "type", "--delay", "0", "--", text)

    def key_combo(self, combo):
        keys = "+".join(XDOTOOL_KEYS.get(k, k) for k in combo.lower().split("+"))
        self._run(self.xdotool, "key", "--clearmodifiers", keys)
