"""Snowman pathing — collects snowflakes from the snowman near Lime every ~2h5m.

Replicates FishSol-Macro RunSnowmanPathing with exact key-hold timings and
resolution-specific coordinates from the AHK source.
"""
from __future__ import annotations

import time
from core.input_controller import InputController


class SnowmanService:
    name = "snowman"

    # FishSol defaults (milliseconds converted to seconds)
    DEFAULT_INTERVAL = 7500.0   # 2h 5m (7500000ms)
    DEFAULT_TIME = 7500.0       # first run after 2h5m

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._anchors: dict[str, list[int]] = {}
        self._pathing_mode: str = "vip"
        self._resolution: str = "1080p"
        self._interval: float = self.DEFAULT_INTERVAL
        self._last_run: float = 0.0
        self._webhook_enabled: bool = False
        self._runs: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        pathing_mode: str = "vip",
        resolution: str = "1080p",
        interval: float = DEFAULT_INTERVAL,
        webhook_enabled: bool = False,
    ) -> None:
        self._anchors = anchors
        self._pathing_mode = pathing_mode
        self._resolution = resolution
        self._interval = interval
        self._webhook_enabled = webhook_enabled

    def should_run(self, elapsed: float) -> bool:
        """Check if snowman pathing is due based on elapsed time since macro start."""
        if self._last_run == 0 and elapsed >= self._interval:
            return True
        if self._last_run > 0 and (elapsed - self._last_run) >= self._interval:
            return True
        return False

    def run(self) -> list[dict[str, str]]:
        """Execute snowman pathing sequence. Returns events."""
        events: list[dict[str, str]] = []
        events.append({"type": "snowman_pathing_start", "message": "Starting snowman pathing"})

        # Reset character first (FishSol: Esc → R → Enter)
        self._reset_character()

        if self._pathing_mode == "non_vip":
            self._run_non_vip()
        elif self._pathing_mode == "abyssal":
            self._run_abyssal()
        else:
            self._run_vip()

        self._runs += 1
        events.append({"type": "snowman_pathing_done", "message": "Snowman pathing complete"})
        return events

    def set_last_run(self, elapsed: float) -> None:
        self._last_run = elapsed

    def _reset_character(self) -> None:
        """FishSol: Esc → R → Enter to reset character position."""
        self._input.send_key("esc", hold_ms=160)
        time.sleep(1.05)
        self._input.send_key("r", hold_ms=160)
        time.sleep(1.05)
        self._input.send_key("enter", hold_ms=160)
        time.sleep(3.2)

    def _release_all_keys(self) -> None:
        for key in ("w", "a", "s", "d", "space", "e"):
            self._input.key_up(key)

    def _teleport_and_scroll(self) -> None:
        """Click teleport menu, NPC, then scroll — resolution-specific from FishSol."""
        if self._resolution == "1080p":
            # FishSol: MouseMove 47,467 → click → 382,126 → click → 80x WheelUp → 45x WheelDown
            self._input.move_to(47, 467, jitter=False)
            time.sleep(0.22)
            self._input.click(47, 467, jitter=False)
            time.sleep(0.22)
            self._input.move_to(382, 126, jitter=False)
            time.sleep(0.22)
            self._input.click(382, 126, jitter=False)
            time.sleep(0.22)
            self._input.scroll(382, 126, 80, "up")
            time.sleep(0.5)
            self._input.scroll(382, 126, 45, "down")
            time.sleep(0.3)
        elif self._resolution == "1440p":
            # FishSol: MouseMove 52,621 → click → 525,158 → click → 80x WheelUp → 35x WheelDown
            self._input.move_to(52, 621, jitter=False)
            time.sleep(0.22)
            self._input.click(52, 621, jitter=False)
            time.sleep(0.22)
            self._input.move_to(525, 158, jitter=False)
            time.sleep(0.22)
            self._input.click(525, 158, jitter=False)
            time.sleep(0.22)
            self._input.scroll(525, 158, 80, "up")
            time.sleep(0.5)
            self._input.scroll(525, 158, 35, "down")
            time.sleep(0.3)
        elif self._resolution == "1366x768":
            # FishSol: MouseMove 26,325 → click → 273,106 → click → 80x WheelUp → 90x WheelDown
            self._input.move_to(26, 325, jitter=False)
            time.sleep(0.22)
            self._input.click(26, 325, jitter=False)
            time.sleep(0.22)
            self._input.move_to(273, 106, jitter=False)
            time.sleep(0.22)
            self._input.click(273, 106, jitter=False)
            time.sleep(0.22)
            self._input.scroll(273, 106, 80, "up")
            time.sleep(0.5)
            self._input.scroll(273, 106, 90, "down")
            time.sleep(0.3)

    def _run_vip(self) -> None:
        """VIP Snowman pathing from FishSol AHK.

        FishSol: teleport_and_scroll → {a Down} sleep 1000 → {s Down} sleep 2700 →
                 {a Up} sleep 2800 → {s Up} → {a Down} sleep 800 {a Up} →
                 {d Down} sleep 200 {d Up} → {w Down} sleep 200 {w Up} →
                 {space Down}+{a Down} → {space Up} sleep 2200 → {a Up} →
                 {e Down} sleep 50 {e Up} sleep 200 → {e Down} sleep 50 {e Up} →
                 release all keys
        """
        self._teleport_and_scroll()

        # Walk to snowman
        self._input.key_down("a")
        time.sleep(1.0)
        self._input.key_down("s")
        time.sleep(2.7)
        self._input.key_up("a")
        time.sleep(2.8)
        self._input.key_up("s")
        time.sleep(0.3)

        self._input.hold_key("a", 800)
        time.sleep(0.3)
        self._input.hold_key("d", 200)
        time.sleep(0.2)
        self._input.hold_key("w", 200)
        time.sleep(0.3)

        # Jump + strafe left
        self._input.key_down("space")
        time.sleep(0.05)
        self._input.key_down("a")
        time.sleep(0.05)
        self._input.key_up("space")
        time.sleep(2.2)
        self._input.key_up("a")
        time.sleep(0.3)

        # Interact with snowman (double E press)
        self._input.hold_key("e", 50)
        time.sleep(0.2)
        self._input.hold_key("e", 50)

        self._release_all_keys()

    def _run_non_vip(self) -> None:
        """Non-VIP Snowman pathing from FishSol AHK.

        FishSol: teleport_and_scroll → {a Down} sleep 1500 → {s Down} sleep 3400 →
                 {a Up} sleep 3400 → {s Up} → {a Down} sleep 800 {a Up} →
                 {d Down} sleep 300 {d Up} → {w Down} sleep 200 {w Up} →
                 {a Down}+{space Down} → {space Up} sleep 2600 → {a Up} →
                 {e Down} sleep 50 {e Up} sleep 200 → {e Down} sleep 50 {e Up} →
                 release all keys
        """
        self._teleport_and_scroll()

        self._input.key_down("a")
        time.sleep(1.5)
        self._input.key_down("s")
        time.sleep(3.4)
        self._input.key_up("a")
        time.sleep(3.4)
        self._input.key_up("s")
        time.sleep(0.3)

        self._input.hold_key("a", 800)
        time.sleep(0.3)
        self._input.hold_key("d", 300)
        time.sleep(0.2)
        self._input.hold_key("w", 200)
        time.sleep(0.3)

        # Strafe left + jump
        self._input.key_down("a")
        time.sleep(0.05)
        self._input.key_down("space")
        time.sleep(0.05)
        self._input.key_up("space")
        time.sleep(2.6)
        self._input.key_up("a")
        time.sleep(0.3)

        self._input.hold_key("e", 50)
        time.sleep(0.2)
        self._input.hold_key("e", 50)

        self._release_all_keys()

    def _run_abyssal(self) -> None:
        """Abyssal Snowman pathing from FishSol AHK.

        FishSol: teleport_and_scroll → abyssal NPC search →
                 {a Down} sleep 1000 → {s Down} sleep 1400 → {a Up} sleep 2100 →
                 {s Up} → {a Down} sleep 600 {a Up} → {d Down} sleep 150 {d Up} →
                 {w Down} sleep 150 {w Up} → {space Down}+{a Down} → {space Up} sleep 1500 →
                 {a Up} → {e Down} sleep 50 {e Up} sleep 200 → {e Down} sleep 50 {e Up} →
                 release all keys
        """
        self._teleport_and_scroll()

        # Abyssal NPC search (resolution-specific from FishSol)
        if self._resolution == "1080p":
            self._input.move_to(30, 406, jitter=False)
            time.sleep(0.2)
            self._input.click(30, 406, jitter=False)
            time.sleep(0.2)
            self._input.move_to(947, 335, jitter=False)
            time.sleep(0.2)
            self._input.click(947, 335, jitter=False)
            time.sleep(0.1)
            self._input.move_to(1102, 367, jitter=False)
            time.sleep(0.1)
            self._input.click(1102, 367, jitter=False)
            time.sleep(0.1)
            # Paste search term
            self._input.key_combo("ctrl", "v")  # assumes "Abyssal Hunter" in clipboard
            time.sleep(0.2)
            self._input.move_to(819, 434, jitter=False)
            time.sleep(0.2)
            self._input.scroll(819, 434, 100, "up")
            time.sleep(0.2)
            self._input.click(819, 434, jitter=False)
            time.sleep(0.2)
            # PixelSearch for pink pixel (0xfc7f98) in 576,626,666,645 — if not found, click 623,634
            # Then click 1412,296
            self._input.move_to(1412, 296, jitter=False)
            time.sleep(0.2)
            self._input.click(1412, 296, jitter=False)
            time.sleep(0.2)
        elif self._resolution == "1440p":
            self._input.move_to(40, 541, jitter=False)
            time.sleep(0.2)
            self._input.click(40, 541, jitter=False)
            time.sleep(0.2)
            self._input.move_to(1262, 447, jitter=False)
            time.sleep(0.2)
            self._input.click(1262, 447, jitter=False)
            time.sleep(0.1)
            self._input.move_to(1469, 489, jitter=False)
            time.sleep(0.1)
            self._input.click(1469, 489, jitter=False)
            time.sleep(0.1)
            self._input.key_combo("ctrl", "v")
            time.sleep(0.2)
            self._input.move_to(1092, 579, jitter=False)
            time.sleep(0.2)
            self._input.scroll(1092, 579, 100, "up")
            time.sleep(0.2)
            self._input.click(1092, 579, jitter=False)
            time.sleep(0.2)
            self._input.move_to(1883, 395, jitter=False)
            time.sleep(0.2)
            self._input.click(1883, 395, jitter=False)
            time.sleep(0.2)
        elif self._resolution == "1366x768":
            self._input.move_to(21, 289, jitter=False)
            time.sleep(0.2)
            self._input.click(21, 289, jitter=False)
            time.sleep(0.2)
            self._input.move_to(675, 239, jitter=False)
            time.sleep(0.2)
            self._input.click(675, 239, jitter=False)
            time.sleep(0.1)
            self._input.move_to(786, 261, jitter=False)
            time.sleep(0.1)
            self._input.click(786, 261, jitter=False)
            time.sleep(0.1)
            self._input.key_combo("ctrl", "v")
            time.sleep(0.2)
            self._input.move_to(584, 310, jitter=False)
            time.sleep(0.2)
            self._input.scroll(584, 310, 80, "up")
            time.sleep(0.2)
            self._input.click(584, 310, jitter=False)
            time.sleep(0.2)
            self._input.move_to(1007, 211, jitter=False)
            time.sleep(0.2)
            self._input.click(1007, 211, jitter=False)
            time.sleep(0.2)

        # Walk to snowman (same across resolutions in FishSol)
        self._input.key_down("a")
        time.sleep(1.0)
        self._input.key_down("s")
        time.sleep(1.4)
        self._input.key_up("a")
        time.sleep(2.1)
        self._input.key_up("s")
        time.sleep(0.3)

        self._input.hold_key("a", 600)
        time.sleep(0.3)
        self._input.hold_key("d", 150)
        time.sleep(0.2)
        self._input.hold_key("w", 150)
        time.sleep(0.3)

        # Jump + strafe left
        self._input.key_down("space")
        time.sleep(0.05)
        self._input.key_down("a")
        time.sleep(0.05)
        self._input.key_up("space")
        time.sleep(1.5)
        self._input.key_up("a")
        time.sleep(0.3)

        # Interact
        self._input.hold_key("e", 50)
        time.sleep(0.2)
        self._input.hold_key("e", 50)

        self._release_all_keys()

    def snapshot(self) -> dict:
        return {
            "runs": self._runs,
            "last_run": self._last_run,
            "interval": self._interval,
            "pathing_mode": self._pathing_mode,
        }
