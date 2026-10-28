"""Backend macOS : Accessibilité (AppleScript / System Events) + Quartz (ctypes).

Prérequis : autoriser le terminal ou l'application qui lance Fukuroku dans
Réglages Système → Confidentialité et sécurité → Accessibilité (et
« Enregistrement de l'écran » pour la détection par pixel).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import subprocess
import time

from ..geometry import Rect
from .base import Backend, BackendError, WindowInfo

_LIST_SCRIPT = r'''
set out to ""
tell application "System Events"
  repeat with p in (every process whose background only is false)
    try
      set pname to name of p
      set ppid to unix id of p
      set i to 0
      repeat with w in (every window of p)
        set i to i + 1
        try
          set {x, y} to position of w
          set {ww, hh} to size of w
          set m to false
          try
            set m to value of attribute "AXMinimized" of w
          end try
          set out to out & ppid & tab & pname & tab & i & tab & x & tab & y & tab & ww & tab & hh & tab & m & tab & (name of w) & linefeed
        end try
      end repeat
    end try
  end repeat
end tell
return out
'''

KEY_CODES = {"enter": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 117, "escape": 53, "left": 123,
             "right": 124, "down": 125, "up": 126, "home": 115, "end": 119, "page_up": 116, "page_down": 121,
             "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101,
             "f10": 109, "f11": 103, "f12": 111}
MODS = {"cmd": "command down", "ctrl": "control down", "alt": "option down", "shift": "shift down"}


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class CGRect(ctypes.Structure):
    _fields_ = [("origin", CGPoint), ("size", CGSize)]


def parse_window_list(output: str) -> list[WindowInfo]:
    out = []
    for line in output.splitlines():
        parts = line.split("\t", 8)
        if len(parts) < 9:
            continue
        pid, pname, idx, x, y, w, h, minimized, title = parts
        try:
            rect = Rect(int(float(x)), int(float(y)), int(float(w)), int(float(h)))
        except ValueError:
            continue
        out.append(WindowInfo(f"{pid}:{idx}", title, pname, rect, int(pid), "", minimized.strip() == "true"))
    return out


def _as_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MacOSBackend(Backend):
    name = "macOS (Accessibilité + Quartz)"
    capabilities = {"windows", "move", "click", "keys", "screens"}

    def __init__(self):
        self.cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices")
                                          or "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        self.cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation")
                                          or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        cg = self.cg
        cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
        cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
        cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        cg.CGEventCreate.restype = ctypes.c_void_p
        cg.CGEventCreate.argtypes = [ctypes.c_void_p]
        cg.CGEventGetLocation.restype = CGPoint
        cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        cg.CGWarpMouseCursorPosition.argtypes = [CGPoint]
        cg.CGDisplayBounds.restype = CGRect
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                              ctypes.POINTER(ctypes.c_uint32)]
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]

    def diagnostics(self):
        return ["Autorisez l'accès « Accessibilité » (et « Enregistrement de l'écran » pour la détection par pixel) "
                "dans Réglages Système → Confidentialité et sécurité."]

    def _osascript(self, script: str) -> str:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            raise BackendError(res.stderr.strip())
        return res.stdout

    def _window_ref(self, handle) -> str:
        pid, idx = str(handle).split(":")
        return f"window {int(idx)} of (first process whose unix id is {int(pid)})"

    def _tell(self, body: str) -> None:
        self._osascript(f'tell application "System Events"\n{body}\nend tell')

    # ------------------------------------------------------------------ fenêtres
    def list_windows(self):
        return parse_window_list(self._osascript(_LIST_SCRIPT))

    def move_resize(self, handle, rect):
        ref = self._window_ref(handle)
        self._tell(f"set position of {ref} to {{{rect.x}, {rect.y}}}\nset size of {ref} to {{{rect.w}, {rect.h}}}")

    def bring_to_front(self, handle):
        self._tell(f'perform action "AXRaise" of {self._window_ref(handle)}')

    def focus(self, handle):
        pid = int(str(handle).split(":")[0])
        self._tell(f'set frontmost of (first process whose unix id is {pid}) to true\n'
                   f'perform action "AXRaise" of {self._window_ref(handle)}')

    def minimize(self, handle):
        self._tell(f'set value of attribute "AXMinimized" of {self._window_ref(handle)} to true')

    def close(self, handle):
        ref = self._window_ref(handle)
        self._tell(f'perform action "AXPress" of (first button of {ref} whose subrole is "AXCloseButton")')

    def screens(self):
        ids = (ctypes.c_uint32 * 16)()
        count = ctypes.c_uint32()
        self.cg.CGGetActiveDisplayList(16, ids, ctypes.byref(count))
        rects = []
        for i in range(count.value):
            b = self.cg.CGDisplayBounds(ids[i])
            rects.append(Rect(int(b.origin.x), int(b.origin.y), int(b.size.width), int(b.size.height)))
        return sorted(rects, key=lambda r: (r.x, r.y)) or [Rect(0, 0, 1440, 900)]

    # ------------------------------------------------------------------ entrées
    def cursor_pos(self):
        ev = self.cg.CGEventCreate(None)
        p = self.cg.CGEventGetLocation(ev)
        self.cf.CFRelease(ev)
        return (int(p.x), int(p.y))

    def set_cursor_pos(self, x, y):
        self.cg.CGWarpMouseCursorPosition(CGPoint(x, y))

    def click(self, x, y, button="left", restore_cursor=True):
        old = self.cursor_pos()
        # kCGEventLeftMouseDown=1/Up=2, RightMouseDown=3/Up=4, OtherMouseDown=25/Up=26
        down, up, btn = {"left": (1, 2, 0), "right": (3, 4, 1), "middle": (25, 26, 2)}.get(button, (1, 2, 0))
        for etype in (down, up):
            ev = self.cg.CGEventCreateMouseEvent(None, etype, CGPoint(x, y), btn)
            self.cg.CGEventPost(0, ev)
            self.cf.CFRelease(ev)
            time.sleep(0.005)
        if restore_cursor:
            self.set_cursor_pos(*old)

    def type_text(self, text):
        self._tell(f"keystroke {_as_quote(text)}")

    def key_combo(self, combo):
        parts = combo.lower().split("+")
        mods = [MODS[p] for p in parts if p in MODS]
        keys = [p for p in parts if p not in MODS]
        if not keys:
            return
        key = keys[-1]
        using = f" using {{{', '.join(mods)}}}" if mods else ""
        if key in KEY_CODES:
            self._tell(f"key code {KEY_CODES[key]}{using}")
        else:
            self._tell(f"keystroke {_as_quote(key)}{using}")
