"""Manette (ControllerHooker) : boutons, combinaisons et lecture d'état.

Les noms de boutons reprennent l'énumération ``GamePadButtons`` d'origine, y
compris les combinaisons (« DPadLeftPlusLeftButton »…).  La lecture d'état
utilise XInput sous Windows et pygame (optionnel) ailleurs.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Callable

GAMEPAD_BUTTONS = [
    "LeftThumbLeft", "LeftThumbUp", "LeftThumbRight", "LeftThumbDown", "LeftThumbPress",
    "RightThumbLeft", "RightThumbUp", "RightThumbRight", "RightThumbRightPlusLeftButton",
    "RightThumbLeftPlusLeftButton", "RightThumbDown", "RightThumbPress", "A", "X", "B", "Y",
    "DPadLeft", "DPadRight", "DPadUp", "DPadDown",
    "DPadLeftPlusLeftButton", "DPadRightPlusLeftButton", "DPadDownPlusLeftButton", "DPadUpPlusLeftButton",
    "DPadLeftPlusRightButton", "DPadUpPlusRightButton", "DPadRightPlusRightButton", "DPadDownPlusRightButton",
    "DPadLeftPlusLeftPlusRightButton", "DPadUpPlusLeftPlusRightButton", "DPadRightPlusLeftPlusRightButton",
    "DPadDownPlusLeftPlusRightButton", "Select", "Start", "RightTrigger", "LeftTrigger", "RightButton", "LeftButton",
]

STICK_THRESHOLD = 0.6


def resolve_combo(pressed: str, held: set[str]) -> str:
    """Nom GamePadButtons d'un appui compte tenu des gâchettes hautes maintenues (LB/RB)."""
    lb, rb = "LeftButton" in held, "RightButton" in held
    if pressed.startswith("DPad"):
        if lb and rb:
            return f"{pressed}PlusLeftPlusRightButton"
        if lb:
            return f"{pressed}PlusLeftButton"
        if rb:
            return f"{pressed}PlusRightButton"
    if pressed in ("RightThumbRight", "RightThumbLeft") and lb:
        return f"{pressed}PlusLeftButton"
    return pressed


def stick_direction(x: float, y: float, prefix: str) -> str | None:
    """Direction d'un stick analogique (y positif vers le haut)."""
    if max(abs(x), abs(y)) < STICK_THRESHOLD:
        return None
    if abs(x) >= abs(y):
        return f"{prefix}Right" if x > 0 else f"{prefix}Left"
    return f"{prefix}Up" if y > 0 else f"{prefix}Down"


class EdgeDetector:
    """Transforme des états successifs en événements « appui » avec combinaisons."""

    MODIFIER_ONLY = {"LeftButton", "RightButton"}

    def __init__(self):
        self.prev: set[str] = set()

    def update(self, state: set[str]) -> list[str]:
        new = state - self.prev
        self.prev = set(state)
        events = []
        for name in sorted(new):
            combo = resolve_combo(name, state)
            events.append(combo)
        # LB/RB seuls génèrent aussi un événement (ex. cycle de tables), sauf s'ils servent de modificateur.
        return [e for e in events if e not in self.MODIFIER_ONLY or not (state - self.MODIFIER_ONLY)]


# ---------------------------------------------------------------- lecture d'état
_XINPUT_BITS = {
    0x0001: "DPadUp", 0x0002: "DPadDown", 0x0004: "DPadLeft", 0x0008: "DPadRight", 0x0010: "Start",
    0x0020: "Select", 0x0040: "LeftThumbPress", 0x0080: "RightThumbPress", 0x0100: "LeftButton",
    0x0200: "RightButton", 0x1000: "A", 0x2000: "B", 0x4000: "X", 0x8000: "Y",
}


def _xinput_reader():
    import ctypes

    class GAMEPAD(ctypes.Structure):
        _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                    ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short),
                    ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]

    class STATE(ctypes.Structure):
        _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", GAMEPAD)]

    dll = None
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(name)
            break
        except OSError:
            continue
    if dll is None:
        return None

    def read() -> set[str] | None:
        st = STATE()
        if dll.XInputGetState(0, ctypes.byref(st)) != 0:
            return None
        g = st.Gamepad
        out = {name for bit, name in _XINPUT_BITS.items() if g.wButtons & bit}
        if g.bLeftTrigger > 100:
            out.add("LeftTrigger")
        if g.bRightTrigger > 100:
            out.add("RightTrigger")
        for d in (stick_direction(g.sThumbLX / 32767, g.sThumbLY / 32767, "LeftThumb"),
                  stick_direction(g.sThumbRX / 32767, g.sThumbRY / 32767, "RightThumb")):
            if d:
                out.add(d)
        return out

    return read


def _pygame_reader():
    try:
        import os
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
    except ImportError:
        return None
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        return None
    js = pygame.joystick.Joystick(0)
    js.init()
    # Disposition SDL GameController / Xbox la plus courante.
    names = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LeftButton", 5: "RightButton", 6: "Select", 7: "Start",
             8: "LeftThumbPress", 9: "RightThumbPress"}

    def read() -> set[str]:
        pygame.event.pump()
        out = {n for i, n in names.items() if i < js.get_numbuttons() and js.get_button(i)}
        if js.get_numhats():
            hx, hy = js.get_hat(0)
            if hx < 0: out.add("DPadLeft")
            if hx > 0: out.add("DPadRight")
            if hy > 0: out.add("DPadUp")
            if hy < 0: out.add("DPadDown")
        axes = [js.get_axis(i) for i in range(js.get_numaxes())]
        if len(axes) >= 2 and (d := stick_direction(axes[0], -axes[1], "LeftThumb")):
            out.add(d)
        if len(axes) >= 5 and (d := stick_direction(axes[3], -axes[4], "RightThumb")):
            out.add(d)
        if len(axes) >= 6:
            if axes[2] > 0.5: out.add("LeftTrigger")
            if axes[5] > 0.5: out.add("RightTrigger")
        return out

    return read


class GamepadListener:
    def __init__(self, on_button: Callable[[str], None], poll_interval: float = 0.016):
        self.on_button = on_button
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.reader = (_xinput_reader() if sys.platform == "win32" else None) or _pygame_reader()

    @property
    def available(self) -> bool:
        return self.reader is not None

    def start(self) -> bool:
        if not self.available:
            return False
        self._thread = threading.Thread(target=self._run, name="gamepad", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def vibrate(self, duration_s: float = 0.35, strength: float = 0.7) -> bool:
        """Vibration « c'est votre tour » (XInput sous Windows, rumble SDL ailleurs)."""
        return vibrate(duration_s, strength)

    def _run(self) -> None:
        edges = EdgeDetector()
        while not self._stop.is_set():
            state = self.reader() or set()
            for name in edges.update(state):
                self.on_button(name)
            time.sleep(self.poll_interval)


def vibrate(duration_s: float = 0.35, strength: float = 0.7) -> bool:
    level = max(0, min(65535, int(strength * 65535)))
    if sys.platform == "win32":
        import ctypes

        class VIBRATION(ctypes.Structure):
            _fields_ = [("wLeftMotorSpeed", ctypes.c_ushort), ("wRightMotorSpeed", ctypes.c_ushort)]

        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                dll = ctypes.WinDLL(name)
                break
            except OSError:
                continue
        else:
            return False
        if dll.XInputSetState(0, ctypes.byref(VIBRATION(level, level))) != 0:
            return False
        threading.Timer(duration_s, lambda: dll.XInputSetState(0, ctypes.byref(VIBRATION(0, 0)))).start()
        return True
    try:
        import pygame
        if pygame.joystick.get_init() and pygame.joystick.get_count():
            return bool(pygame.joystick.Joystick(0).rumble(strength, strength, int(duration_s * 1000)))
    except Exception:
        pass
    return False
