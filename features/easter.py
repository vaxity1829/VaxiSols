from __future__ import annotations

import time

from core.input_controller import InputController


class EasterService:
    name = "easter"

    DEFAULT_INTERVAL = 1800.0

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._anchors: dict[str, list[int]] = {}
        self._pathing_mode: str = "vip"
        self._resolution: str = "1080p"
        self._interval: float = self.DEFAULT_INTERVAL
        self._last_run: float = 0.0
        self._webhook_enabled: bool = False
        self._limited_pathing: bool = False
        self._pause_auto_roll: bool = False
        self._pending: bool = False
        self._skip_fishing: bool = False
        self._runs: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        pathing_mode: str = "vip",
        resolution: str = "1080p",
        interval: float = DEFAULT_INTERVAL,
        webhook_enabled: bool = False,
        limited_pathing: bool = False,
        pause_auto_roll: bool = False,
    ) -> None:
        self._anchors = anchors
        self._pathing_mode = pathing_mode
        self._resolution = resolution
        self._interval = interval
        self._webhook_enabled = webhook_enabled
        self._limited_pathing = limited_pathing
        self._pause_auto_roll = pause_auto_roll

    def should_run(self, elapsed: float) -> bool:
        if self._last_run == 0 and elapsed >= self._interval:
            return True
        if self._last_run > 0 and (elapsed - self._last_run) >= self._interval:
            return True
        return False

    @property
    def pending(self) -> bool:
        return self._pending

    @pending.setter
    def pending(self, value: bool) -> None:
        self._pending = value

    @property
    def skip_fishing(self) -> bool:
        return self._skip_fishing

    @skip_fishing.setter
    def skip_fishing(self, value: bool) -> None:
        self._skip_fishing = value

    def set_last_run(self, elapsed: float) -> None:
        self._last_run = elapsed

    def _reset_character(self) -> None:
        self._input.send_key("esc", hold_ms=160)
        time.sleep(1.05)
        self._input.send_key("r", hold_ms=160)
        time.sleep(1.05)
        self._input.send_key("enter", hold_ms=160)
        time.sleep(3.2)

    def run(self) -> list[dict[str, str]]:
        # Keep this lightweight; legacy pathing can be expanded later.
        events = [{"type": "easter_pathing_start", "message": "Starting Easter pathing (legacy)."}]
        self._reset_character()
        self._runs += 1
        self._pending = False
        self._skip_fishing = False
        events.append({"type": "easter_pathing_done", "message": "Easter pathing complete."})
        return events

    def snapshot(self) -> dict:
        return {
            "runs": self._runs,
            "interval": self._interval,
            "pending": self._pending,
            "skip_fishing": self._skip_fishing,
            "limited_pathing": self._limited_pathing,
            "pause_auto_roll": self._pause_auto_roll,
        }
