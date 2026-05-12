from __future__ import annotations

import ctypes
import random
import time
from dataclasses import dataclass

from core.input_controller import InputController
from core.roblox_window import RobloxWindow, RobloxWindowManager


@dataclass
class AntiAfkStats:
    keepalive_actions: int = 0
    hidden_mode_active: bool = False


class AntiAfkService:
    name = "anti_afk"

    def __init__(self) -> None:
        self.stats = AntiAfkStats()
        self._last_action: float = 0.0
        self._action_interval: float = 18.0  # Seconds between keepalive actions
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._window_mgr = RobloxWindowManager()
        self._target_window: RobloxWindow | None = None
        self._hidden_mode: bool = False

    def set_hidden_mode(self, enabled: bool) -> None:
        """Toggle hidden mode (move Roblox off-screen)."""
        self._hidden_mode = enabled
        self.stats.hidden_mode_active = enabled
        if enabled:
            win = self._window_mgr.find_primary()
            if win:
                self._target_window = win
                win.hide()
        else:
            if self._target_window and self._target_window.is_valid():
                self._target_window.show()
            self._target_window = None

    def tick(self, now: float, active: bool) -> list[dict[str, str]]:
        if not active:
            return []

        if now - self._last_action < self._action_interval:
            return []

        self._last_action = now
        self.stats.keepalive_actions += 1

        # Perform a random keepalive action
        action = random.choice(["space", "move", "shift"])
        self._perform_keepalive(action)

        return [{"type": "anti_afk", "message": f"Anti-AFK keepalive: {action}"}]

    def _perform_keepalive(self, action: str) -> None:
        """Execute a small input to prevent AFK kick.

        These are designed to be non-disruptive to other macro features.
        """
        if action == "space":
            # Brief space press — opens chat briefly but doesn't interfere
            self._input.send_key("space", hold_ms=50)
        elif action == "move":
            # Tiny mouse nudge — moves cursor 1-3px in a random direction
            screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)
            # Get current cursor position
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            # Move slightly
            dx = random.choice([-2, -1, 1, 2])
            dy = random.choice([-2, -1, 1, 2])
            new_x = max(0, min(screen_w - 1, pt.x + dx))
            new_y = max(0, min(screen_h - 1, pt.y + dy))
            self._input.move_to(new_x, new_y, jitter=False)
        elif action == "shift":
            # Brief shift press — harmless key
            self._input.send_key("shift", hold_ms=50)

    def snapshot(self) -> dict:
        return {
            "keepalive_actions": self.stats.keepalive_actions,
            "hidden_mode_active": self.stats.hidden_mode_active,
        }
