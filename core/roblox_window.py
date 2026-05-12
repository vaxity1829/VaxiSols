from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass
from typing import Sequence


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# Windows constants
GWL_STYLE = -16
WS_VISIBLE = 0x10000000
SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
HWND_NOTOPMOST = -2
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010


@dataclass
class WindowRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)


@dataclass
class RobloxWindow:
    hwnd: int
    pid: int
    title: str
    rect: WindowRect
    is_visible: bool

    @staticmethod
    def client_screen_origin(hwnd: int) -> tuple[int, int]:
        """Top-left of the client area in screen pixels (handles title bars & multi-monitor)."""
        pt = _POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return (int(pt.x), int(pt.y))

    @staticmethod
    def get_client_size(hwnd: int) -> tuple[int, int]:
        """Client area width × height (same units as anchor calibration / GetPixel)."""
        rect = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        return int(rect.right - rect.left), int(rect.bottom - rect.top)

    @staticmethod
    def client_point_to_screen(hwnd: int, cx: int, cy: int) -> tuple[int, int]:
        """Map client-relative coordinates to screen pixels (authoritative vs. manual offset math)."""
        pt = _POINT(cx, cy)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return int(pt.x), int(pt.y)

    @staticmethod
    def client_center_screen(hwnd: int) -> tuple[int, int]:
        """Screen coordinates of the client area center (camera zoom / neutral look)."""
        cw, ch = RobloxWindow.get_client_size(hwnd)
        return RobloxWindow.client_point_to_screen(hwnd, max(0, cw // 2), max(0, ch // 2))

    @classmethod
    def from_hwnd(cls, hwnd: int) -> RobloxWindow | None:
        if not user32.IsWindow(hwnd):
            return None
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title_buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title_buf, 256)
        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        return cls(
            hwnd=hwnd,
            pid=pid.value,
            title=title_buf.value,
            rect=WindowRect(rect.left, rect.top, rect.right, rect.bottom),
            is_visible=bool(style & WS_VISIBLE),
        )

    def is_valid(self) -> bool:
        return user32.IsWindow(self.hwnd)

    def bring_to_foreground(self) -> bool:
        """Bring the Roblox window to the foreground (AttachThreadInput for Win10+ quirks)."""
        kernel32 = ctypes.windll.kernel32
        user32.ShowWindow(self.hwnd, SW_RESTORE)

        hwnd = self.hwnd
        cur_tid = kernel32.GetCurrentThreadId()
        fg = user32.GetForegroundWindow()
        fg_tid = 0
        if fg:
            fg_tid = user32.GetWindowThreadProcessId(fg, ctypes.byref(wt.DWORD(0)))
        attached = False
        try:
            if fg_tid and fg_tid != cur_tid:
                attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
        return True

    def minimize(self) -> bool:
        user32.ShowWindow(self.hwnd, SW_MINIMIZE)
        return True

    def hide(self) -> bool:
        """Move window off-screen for hidden mode (MultiScope stealth)."""
        user32.MoveWindow(
            self.hwnd, -32000, -32000,
            self.rect.width, self.rect.height, True
        )
        return True

    def show(self) -> bool:
        """Restore window from hidden mode to its original position."""
        user32.ShowWindow(self.hwnd, SW_SHOW)
        self.bring_to_foreground()
        return True

    def set_topmost(self, topmost: bool = True) -> bool:
        """Set or remove always-on-top flag."""
        z_order = HWND_TOPMOST if topmost else HWND_NOTOPMOST
        return bool(user32.SetWindowPos(
            self.hwnd, z_order, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        ))

    def refresh_rect(self) -> WindowRect:
        """Re-read the window position/size."""
        rect = wt.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        self.rect = WindowRect(rect.left, rect.top, rect.right, rect.bottom)
        return self.rect


class RobloxWindowManager:
    """Find and manage Roblox game windows."""

    # Known Roblox window class names
    ROBLOX_CLASSES = {"WINDOWSCLIENT", "RobloxPlayerBeta"}

    def find_all(self) -> Sequence[RobloxWindow]:
        """Find all Roblox game windows currently open."""
        results: list[RobloxWindow] = []

        def _enum_callback(hwnd, _):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            # Get class name
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value

            if class_name in self.ROBLOX_CLASSES:
                win = RobloxWindow.from_hwnd(hwnd)
                if win:
                    results.append(win)

        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        callback = callback_type(_enum_callback)
        user32.EnumWindows(callback, 0)
        return results

    def find_primary(self) -> RobloxWindow | None:
        """Find the first (primary) Roblox window."""
        windows = self.find_all()
        return windows[0] if windows else None

    def find_by_pid(self, pid: int) -> RobloxWindow | None:
        """Find a specific Roblox window by its process ID."""
        for win in self.find_all():
            if win.pid == pid:
                return win
        return None

    @staticmethod
    def is_roblox_running() -> bool:
        """Quick check if any Roblox window exists."""
        found = False

        def _cb(hwnd, _):
            nonlocal found
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            if class_buf.value in RobloxWindowManager.ROBLOX_CLASSES:
                found = True
            return True

        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        user32.EnumWindows(callback_type(_cb), 0)
        return found
