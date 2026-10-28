"""Sélection automatique du backend selon le système."""

from __future__ import annotations

import sys

from .base import Backend, BackendError, WindowInfo
from .dummy import DummyBackend


def create_backend(force: str | None = None) -> Backend:
    choice = force or {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    if choice == "simulation":
        return DummyBackend()
    if choice == "windows":
        from .windows import WindowsBackend
        return WindowsBackend()
    if choice == "macos":
        from .macos import MacOSBackend
        return MacOSBackend()
    from .linux_x11 import LinuxX11Backend
    return LinuxX11Backend()


__all__ = ["Backend", "BackendError", "WindowInfo", "DummyBackend", "create_backend"]
