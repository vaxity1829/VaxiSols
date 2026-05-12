from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import random
import time
from typing import Sequence


user32 = ctypes.windll.user32

# SendInput constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
MAPVK_VK_TO_VSC = 0

# Keys that require KEYEVENTF_EXTENDEDKEY with scan codes (arrows, home, etc.)
_EXTENDED_VK_SCAN = frozenset({
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E,
})


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_ulong),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_ulong),
    ]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    _anonymous_ = ("union",)
    _fields_ = [("type", wt.DWORD), ("union", _U)]


# Virtual key codes
VK_MAP = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "shift": 0x10,
    "ctrl": 0x11, "alt": 0x12, "pause": 0x13, "capslock": 0x14,
    "esc": 0x1B, "space": 0x20, "pageup": 0x21, "pagedown": 0x22,
    "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26,
    "right": 0x27, "down": 0x28, "insert": 0x2D, "delete": 0x2E,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "numlock": 0x90, "scrolllock": 0x91,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
}


def _jitter(max_px: int = 3) -> int:
    """Small random offset for human-like input."""
    return random.randint(-max_px, max_px)


def _human_delay(min_ms: float = 30, max_ms: float = 80) -> None:
    """Small random delay between actions."""
    time.sleep(random.uniform(min_ms, max_ms) / 1000.0)


def _allow_set_foreground() -> None:
    """Let the next focus/click bring a game window forward (helps Roblox + WebView2)."""
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(-1)
    except Exception:
        pass


def _resolve_vk(key: str) -> int:
    """Virtual key for SendInput; single printable chars use VkKeyScan (e.g. '/')."""
    k = key.lower()
    if k in VK_MAP:
        return VK_MAP[k]
    if len(key) == 1:
        ch = ord(key)
        scanned = user32.VkKeyScanW(ch)
        if scanned != 0xFFFF:
            return int(scanned & 0xFF)
        return ch
    return 0x41


def _pyautogui_key_name(key: str) -> str:
    """Name expected by ``pyautogui.keyDown`` / ``keyUp``."""
    k = key.lower()
    aliases = {
        "esc": "esc",
        "escape": "esc",
        "enter": "enter",
        "return": "enter",
        "space": "space",
        "tab": "tab",
        "shift": "shift",
        "ctrl": "ctrl",
        "alt": "alt",
        "backspace": "backspace",
        "delete": "delete",
        "insert": "insert",
        "pageup": "pageup",
        "pagedown": "pagedown",
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
    }
    if k in aliases:
        return aliases[k]
    if len(key) == 1:
        return key.lower()
    return k


class InputController:
    """Low-level input sender using Windows SendInput API.

    Works even when the target window is in the background (for most games).
    Falls back to pyautogui when needed.
    """

    def __init__(self, jitter_px: int = 3, delay_ms: float = 50) -> None:
        self.jitter_px = jitter_px
        self.delay_ms = delay_ms

    # ── Mouse ──

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
        jitter: bool = True,
    ) -> None:
        """Click at screen coordinates with optional random offset."""
        _allow_set_foreground()
        if jitter:
            x += _jitter(self.jitter_px)
            y += _jitter(self.jitter_px)

        try:
            import pyautogui

            pyautogui.FAILSAFE = False
            pyautogui.moveTo(int(x), int(y), duration=0.03)
            btn_map = {"left": "left", "right": "right", "middle": "middle"}
            pg_btn = btn_map.get(button, "left")
            for _ in range(clicks):
                pyautogui.click(button=pg_btn)
                _human_delay(40, 80)
            return
        except Exception:
            pass

        self._move_mouse(x, y)
        _human_delay(20, 50)

        down_flag = {
            "left": MOUSEEVENTF_LEFTDOWN,
            "right": MOUSEEVENTF_RIGHTDOWN,
            "middle": MOUSEEVENTF_MIDDLEDOWN,
        }[button]
        up_flag = {
            "left": MOUSEEVENTF_LEFTUP,
            "right": MOUSEEVENTF_RIGHTUP,
            "middle": MOUSEEVENTF_MIDDLEUP,
        }[button]

        for _ in range(clicks):
            self._send_mouse(down_flag)
            _human_delay(30, 60)
            self._send_mouse(up_flag)
            _human_delay(50, 100)

    def move_to(self, x: int, y: int, jitter: bool = True) -> None:
        """Move mouse to screen coordinates."""
        _allow_set_foreground()
        if jitter:
            x += _jitter(self.jitter_px)
            y += _jitter(self.jitter_px)
        try:
            import pyautogui

            pyautogui.FAILSAFE = False
            pyautogui.moveTo(int(x), int(y), duration=0.03)
            return
        except Exception:
            pass
        self._move_mouse(x, y)

    def scroll(self, x: int, y: int, clicks: int = 3, direction: str = "down") -> None:
        """Scroll mouse wheel at screen position (wheel events must not use ABSOLUTE move flags)."""
        _allow_set_foreground()
        try:
            import pyautogui

            pyautogui.FAILSAFE = False
            pyautogui.moveTo(int(x), int(y), duration=0.03)
            sign = -1 if direction == "down" else 1
            pyautogui.scroll(sign * clicks)
            return
        except Exception:
            pass
        self._move_mouse(x, y)
        delta = -120 * clicks if direction == "down" else 120 * clicks
        inp = INPUT(type=INPUT_MOUSE)
        inp.union.mi = MOUSEINPUT(
            dx=0, dy=0, mouseData=delta & 0xFFFFFFFF,
            dwFlags=MOUSEEVENTF_WHEEL,
        )
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    # ── Keyboard ──

    def send_key(self, key: str, hold_ms: float = 0) -> None:
        """Press and release a key. Longer default hold (~150 ms) so Roblox registers taps.

        Tries ``pyautogui`` first (often more reliable with Roblox), then scan-code
        ``SendInput``, then plain VK ``SendInput``.
        """
        _allow_set_foreground()
        vk = _resolve_vk(key)
        effective_hold = float(hold_ms) if hold_ms > 0 else 150.0
        dwell = max(effective_hold, 80.0) / 1000.0

        used_py = False
        try:
            import pyautogui

            pyautogui.FAILSAFE = False
            pg = _pyautogui_key_name(key)
            pyautogui.keyDown(pg)
            time.sleep(dwell)
            pyautogui.keyUp(pg)
            used_py = True
        except Exception:
            pass

        if not used_py:
            if not self._send_key_event_scan(vk, key_up=False):
                self._send_key_event_vk_only(vk, key_up=False)
            time.sleep(dwell)
            if not self._send_key_event_scan(vk, key_up=True):
                self._send_key_event_vk_only(vk, key_up=True)

        time.sleep(random.uniform(170.0, 300.0) / 1000.0)

    def hold_key(self, key: str, duration_ms: float = 500) -> None:
        """Hold a key for a specified duration."""
        self.send_key(key, hold_ms=duration_ms)

    def key_down(self, key: str) -> None:
        """Press and hold a key down (does not release). Use key_up() to release."""
        vk = _resolve_vk(key)
        if not self._send_key_event_scan(vk, key_up=False):
            self._send_key_event_vk_only(vk, key_up=False)

    def key_up(self, key: str) -> None:
        """Release a previously held key."""
        vk = _resolve_vk(key)
        if not self._send_key_event_scan(vk, key_up=True):
            self._send_key_event_vk_only(vk, key_up=True)

    def type_text(self, text: str, interval_ms: float = 50) -> None:
        """Type a string of characters with human-like delays."""
        for char in text:
            self.send_key(char)
            _human_delay(interval_ms * 0.5, interval_ms * 1.5)

    def key_combo(self, *keys: str) -> None:
        """Press a key combination (e.g., key_combo('ctrl', 'c'))."""
        for key in keys:
            self._send_key_down(_resolve_vk(key))
            _human_delay(10, 30)

        _human_delay(30, 60)

        for key in reversed(keys):
            self._send_key_up(_resolve_vk(key))
            _human_delay(10, 30)

    # ── Pathing helpers ──

    def walk_path(self, keys: Sequence[tuple[str, float]]) -> None:
        """Execute a sequence of (key, hold_duration_ms) for walking paths.

        Example: [('w', 2000), ('a', 500), ('w', 1000)]
        """
        for key, duration_ms in keys:
            self.hold_key(key, duration_ms)
            _human_delay(50, 150)

    # ── Internal ──

    @staticmethod
    def _move_mouse(x: int, y: int) -> None:
        """Move mouse to absolute screen coordinates."""
        # Convert to normalized absolute coordinates (0-65535 range)
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        norm_x = int(x * 65535 / screen_w) if screen_w else 0
        norm_y = int(y * 65535 / screen_h) if screen_h else 0

        inp = INPUT(type=INPUT_MOUSE)
        inp.union.mi = MOUSEINPUT(
            dx=norm_x, dy=norm_y,
            dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
        )
        inserted = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if inserted != 1:
            try:
                import pyautogui

                pyautogui.FAILSAFE = False
                pyautogui.moveTo(x, y, duration=0)
            except Exception:
                ctypes.windll.user32.SetCursorPos(x, y)

    @staticmethod
    def _send_mouse(flags: int, x: int = 0, y: int = 0) -> None:
        inp = INPUT(type=INPUT_MOUSE)
        inp.union.mi = MOUSEINPUT(dx=x, dy=y, dwFlags=flags)
        if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1:
            return
        # Fallback: legacy mouse_event (some games / drivers reject SendInput)
        if flags & MOUSEEVENTF_LEFTDOWN:
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        elif flags & MOUSEEVENTF_LEFTUP:
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif flags & MOUSEEVENTF_RIGHTDOWN:
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        elif flags & MOUSEEVENTF_RIGHTUP:
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

    @staticmethod
    def _send_key_event_scan(vk: int, key_up: bool) -> bool:
        """Send scan-code key event; return True if a scan code existed and SendInput ran."""
        scan = int(user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)) & 0xFF
        if not scan:
            return False
        flags = KEYEVENTF_SCANCODE
        if key_up:
            flags |= KEYEVENTF_KEYUP
        if vk in _EXTENDED_VK_SCAN:
            flags |= KEYEVENTF_EXTENDEDKEY
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(
            wVk=0,
            wScan=wt.WORD(scan),
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )
        return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1

    @staticmethod
    def _send_key_event_vk_only(vk: int, key_up: bool) -> None:
        fl = KEYEVENTF_KEYUP if key_up else 0
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(wVk=wt.WORD(vk), wScan=0, dwFlags=fl, time=0, dwExtraInfo=0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    @staticmethod
    def _send_key_down(vk: int) -> None:
        if not InputController._send_key_event_scan(vk, key_up=False):
            InputController._send_key_event_vk_only(vk, key_up=False)

    @staticmethod
    def _send_key_up(vk: int) -> None:
        if not InputController._send_key_event_scan(vk, key_up=True):
            InputController._send_key_event_vk_only(vk, key_up=True)
