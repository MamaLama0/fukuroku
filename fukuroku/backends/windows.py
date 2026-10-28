"""Backend Windows (Win32 via ctypes, sans dépendance)."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from ..geometry import Rect
from .base import Backend, WindowInfo

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32")
try:
    dwmapi = ctypes.WinDLL("dwmapi")
except OSError:  # pragma: no cover
    dwmapi = None

try:  # Coordonnées physiques cohérentes en multi-écran / HiDPI.
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
except Exception:  # pragma: no cover
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

_H = wintypes.HWND
for _name, _args in {
    "SetWindowPos": [_H, _H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT],
    "ShowWindow": [_H, ctypes.c_int], "IsIconic": [_H], "IsWindowVisible": [_H],
    "GetWindowRect": [_H, ctypes.POINTER(wintypes.RECT)], "PostMessageW": [_H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
    "SetForegroundWindow": [_H], "BringWindowToTop": [_H], "GetWindowLongW": [_H, ctypes.c_int],
    "SetWindowLongW": [_H, ctypes.c_int, wintypes.LONG],
    "GetWindowTextLengthW": [_H], "GetWindowTextW": [_H, wintypes.LPWSTR, ctypes.c_int],
    "GetClassNameW": [_H, wintypes.LPWSTR, ctypes.c_int],
    "GetWindowThreadProcessId": [_H, ctypes.POINTER(wintypes.DWORD)],
}.items():
    getattr(user32, _name).argtypes = _args
user32.GetForegroundWindow.restype = _H
if dwmapi:
    dwmapi.DwmGetWindowAttribute.argtypes = [_H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                     wintypes.LPARAM)

SW_RESTORE, SW_MINIMIZE = 9, 6
SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE = 0x0004, 0x0010, 0x0002, 0x0001
HWND_TOP = 0
WM_CLOSE = 0x0010
GW_OWNER = 4
GWL_EXSTYLE, GWL_STYLE = -20, -16
WS_CAPTION, SWP_FRAMECHANGED = 0x00C00000, 0x0020
WS_EX_TOOLWINDOW = 0x00000080
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "cmd": 0x5B, "enter": 0x0D, "tab": 0x09, "escape": 0x1B,
      "space": 0x20, "backspace": 0x08, "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
      "page_up": 0x21, "page_down": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
VK.update({chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})


def _rect(r: wintypes.RECT) -> Rect:
    return Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)


class WindowsBackend(Backend):
    name = "Windows (Win32)"
    capabilities = {"windows", "move", "click", "keys", "pixel", "screens"}

    # ------------------------------------------------------------------ fenêtres
    def _process_name(self, hwnd) -> tuple[str, int]:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        name = ""
        if handle:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = buf.value.rsplit("\\", 1)[-1]
            kernel32.CloseHandle(handle)
        return name, pid.value

    def _window_rect(self, hwnd) -> Rect:
        r = wintypes.RECT()
        if dwmapi and dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r),
                                                     ctypes.sizeof(r)) == 0:
            return _rect(r)
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return _rect(r)

    def _is_cloaked(self, hwnd) -> bool:
        if not dwmapi:
            return False
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        return bool(cloaked.value)

    def list_windows(self):
        out: list[WindowInfo] = []

        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd) or self._is_cloaked(hwnd):
                return True
            if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            proc, pid = self._process_name(hwnd)
            out.append(WindowInfo(int(hwnd), title.value, proc, self._window_rect(hwnd), pid, cls.value,
                                  bool(user32.IsIconic(hwnd))))
            return True

        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return out

    def move_resize(self, handle, rect):
        if user32.IsIconic(handle):
            user32.ShowWindow(handle, SW_RESTORE)
        # Compense la bordure invisible de Windows 10/11 (cadre DWM ≠ GetWindowRect).
        outer, inner = wintypes.RECT(), self._window_rect(handle)
        user32.GetWindowRect(handle, ctypes.byref(outer))
        o = _rect(outer)
        dl, dt = inner.x - o.x, inner.y - o.y
        dr, db = o.right - inner.right, o.bottom - inner.bottom
        user32.SetWindowPos(handle, HWND_TOP, rect.x - dl, rect.y - dt, rect.w + dl + dr, rect.h + dt + db,
                            SWP_NOZORDER | SWP_NOACTIVATE)

    def bring_to_front(self, handle):
        user32.SetWindowPos(handle, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def focus(self, handle):
        if user32.IsIconic(handle):
            user32.ShowWindow(handle, SW_RESTORE)
        # Contourne le verrou de premier plan : une frappe Alt synthétique autorise SetForegroundWindow.
        self._send_keys([(VK["alt"], False), (VK["alt"], True)])
        user32.SetForegroundWindow(handle)
        user32.BringWindowToTop(handle)

    def minimize(self, handle):
        user32.ShowWindow(handle, SW_MINIMIZE)

    def close(self, handle):
        user32.PostMessageW(handle, WM_CLOSE, 0, 0)

    def foreground(self):
        return int(user32.GetForegroundWindow() or 0) or None

    def set_title_bar(self, handle, visible):
        style = user32.GetWindowLongW(handle, GWL_STYLE)
        style = (style | WS_CAPTION) if visible else (style & ~WS_CAPTION)
        user32.SetWindowLongW(handle, GWL_STYLE, ctypes.c_long(style).value)
        user32.SetWindowPos(handle, HWND_TOP, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def screens(self):
        out: list[Rect] = []

        def cb(hmon, _hdc, _rect, _):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(hmon, ctypes.byref(info))
            out.append(_rect(info.rcWork))
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
        return sorted(out, key=lambda r: (r.x, r.y)) or [Rect(0, 0, 1920, 1080)]

    # ------------------------------------------------------------------ entrées
    def cursor_pos(self):
        p = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        return (p.x, p.y)

    def set_cursor_pos(self, x, y):
        user32.SetCursorPos(int(x), int(y))

    def _send(self, inputs: list[INPUT]) -> None:
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def click(self, x, y, button="left", restore_cursor=True):
        old = self.cursor_pos()
        self.set_cursor_pos(x, y)
        down, up = MOUSEEVENTF.get(button, MOUSEEVENTF["left"])
        self._send([INPUT(INPUT_MOUSE, _INPUTUNION(mi=MOUSEINPUT(0, 0, 0, down, 0, 0))),
                    INPUT(INPUT_MOUSE, _INPUTUNION(mi=MOUSEINPUT(0, 0, 0, up, 0, 0)))])
        if restore_cursor:
            time.sleep(0.01)
            self.set_cursor_pos(*old)

    def _send_keys(self, keys: list[tuple[int, bool]]) -> None:
        self._send([INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)))
                    for vk, up in keys])

    def type_text(self, text):
        inputs = []
        for ch in text:
            for up in (False, True):
                flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
                inputs.append(INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, ord(ch), flags, 0, 0))))
        self._send(inputs)

    def key_combo(self, combo):
        keys = [VK[k] for k in combo.lower().split("+") if k in VK]
        self._send_keys([(k, False) for k in keys] + [(k, True) for k in reversed(keys)])

    def pixel(self, x, y):
        hdc = user32.GetDC(0)
        try:
            c = gdi32.GetPixel(hdc, int(x), int(y))
        finally:
            user32.ReleaseDC(0, hdc)
        if c == 0xFFFFFFFF:
            return None
        return (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)
