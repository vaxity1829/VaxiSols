from __future__ import annotations

import time
from dataclasses import dataclass

from core.input_controller import InputController
from core.screen_reader import PixelColor, ScreenReader, ScreenRegion


@dataclass
class FishingStats:
    casts: int = 0
    catches: int = 0
    failsafes_triggered: int = 0


# Colors from FishSol-Macro AHK source
WHITE_PIXEL = PixelColor(255, 255, 255)
GREEN_START_PIXEL = PixelColor(0x82, 0xFF, 0x95)  # 0x82ff95 — rejoin start button


class FishingService:
    name = "fishing"

    def __init__(self) -> None:
        self.stats = FishingStats()
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._screen = ScreenReader()
        self._anchors: dict[str, list[int]] = {}
        self._advanced_detection: bool = False
        self._advanced_threshold: int = 25  # pixels left before click (FishSol default)
        self._fishing_failsafe_time: float = 31.0  # seconds (FishSol default)
        self._bar_color: PixelColor | None = None
        self._state: str = "idle"  # idle | waiting_bite | reeling
        self._cast_start: float = 0.0

    def configure(
        self,
        anchors: dict[str, list[int]],
        advanced_detection: bool = False,
        advanced_threshold: int = 25,
        fishing_failsafe_time: float = 31.0,
    ) -> None:
        self._anchors = anchors
        self._advanced_detection = advanced_detection
        self._advanced_threshold = advanced_threshold
        self._fishing_failsafe_time = fishing_failsafe_time

    def tick(self, now: float, active: bool) -> list[dict[str, str]]:
        if not active or not self._anchors:
            return []

        events: list[dict[str, str]] = []

        if self._state == "idle":
            events.extend(self._do_cast())
        elif self._state == "waiting_bite":
            events.extend(self._wait_for_bite(now))
        elif self._state == "reeling":
            events.extend(self._do_reel())

        return events

    def _do_cast(self) -> list[dict[str, str]]:
        """Cast line — FishSol 1080p main loop uses **water click only** here (603,597).

        The fishing-toolbar click (829,218) is used **after** a catch (see ``_do_reel``) and
        once at session start (``prime_fishing_ui``) so the rod UI stays open between casts.
        Clicking the toolbar before every cast toggles the UI and sends clicks to the wrong place.
        """
        events: list[dict[str, str]] = []

        cast_pos = self._anchors.get("fishing_cast_click")
        if cast_pos:
            self._input.move_to(cast_pos[0], cast_pos[1], jitter=False)
            time.sleep(0.3)
            self._input.click(cast_pos[0], cast_pos[1], jitter=False)
            time.sleep(0.3)

        self.stats.casts += 1
        self._state = "waiting_bite"
        self._cast_start = time.time()
        self._bar_color = None
        events.append({
            "type": "fishing_cast",
            "message": "Cast at water (FishSol order: cast click only; toolbar is post-catch / prime).",
        })
        return events

    def _wait_for_bite(self, now: float) -> list[dict[str, str]]:
        """Wait for fish bite by detecting white pixel at bobber position.

        FishSol AHK: PixelSearch, px, py, 866, 593, 865, 593, 0xFFFFFF, 10, Fast RGB
        When white pixel appears → fish bit, sample bar color and start reeling.
        """
        events: list[dict[str, str]] = []

        bobber_pos = self._anchors.get("fishing_bobber_detect")
        if not bobber_pos:
            return events

        # Check for white pixel at bobber (bite detection)
        if self._screen.pixel_matches(bobber_pos[0], bobber_pos[1], WHITE_PIXEL, tolerance=10):
            # Fish bit — FishSol moves to a prep point before sampling bar color (1080p: 950,880).
            bite_prep = self._anchors.get("fishing_bite_prep")
            bar_area = self._anchors.get("fishing_bar_color_sample")
            if bite_prep:
                self._input.move_to(bite_prep[0], bite_prep[1], jitter=False)
                time.sleep(0.05)
            elif bar_area:
                self._input.move_to(bar_area[0] + 2, bar_area[1] + 105, jitter=False)
                time.sleep(0.05)

            # Sample bar color at fishing_bar_color_sample (resolution-specific in FishSol)
            bar_sample = self._anchors.get("fishing_bar_color_sample")
            if bar_sample:
                self._bar_color = self._screen.get_pixel_color(bar_sample[0], bar_sample[1])
            else:
                self._bar_color = None

            self._state = "reeling"
            events.append({"type": "fish_bite", "message": "Fish detected! Starting reel minigame."})
            return events

        # Fishing failsafe — if no bite within timeout, recast
        elapsed = now - self._cast_start
        if elapsed > self._fishing_failsafe_time:
            self._run_fishing_failsafe()
            self.stats.failsafes_triggered += 1
            self._state = "idle"
            events.append({
                "type": "fishing_failsafe",
                "message": f"Fishing failsafe triggered after {self._fishing_failsafe_time}s — recasting.",
            })

        return events

    def _do_reel(self) -> list[dict[str, str]]:
        """Reel the fish using the minigame bar detection.

        FishSol normal detection:
          PixelSearch, FoundX, FoundY, 513, 531, 856, 549, barColor, 5, Fast RGB
          If found → bar is visible, do nothing
          If not found → click to keep the bar in range

        FishSol advanced detection:
          Find bar left edge, scan right to find bar width
          If barWidth < threshold → click (bar about to exit range)
          Otherwise → don't click (bar still well within range)
        """
        events: list[dict[str, str]] = []

        bar_region = self._anchors.get("fishing_bar_region")
        if not bar_region or not self._bar_color:
            # Fallback: click at center of bar region area
            if bar_region:
                cx = (bar_region[0] + bar_region[2]) // 2
                cy = (bar_region[1] + bar_region[3]) // 2
                self._input.click(cx, cy)
            time.sleep(0.05)
            return events

        region = ScreenRegion(
            x=bar_region[0], y=bar_region[1],
            width=bar_region[2] - bar_region[0],
            height=bar_region[3] - bar_region[1],
        )

        if self._advanced_detection:
            self._advanced_reel(region)
        else:
            self._normal_reel(region)

        # Check if minigame ended (white pixel gone at bobber)
        bobber_pos = self._anchors.get("fishing_bobber_detect")
        if bobber_pos:
            if not self._screen.pixel_matches(bobber_pos[0], bobber_pos[1], WHITE_PIXEL, tolerance=10):
                # Minigame over — fish caught or lost
                self.stats.catches += 1
                self._state = "idle"
                events.append({"type": "fish_caught", "message": "Fish caught!"})

                # FishSol: MouseMove 829,218 → Sleep 700 → click (reset rod UI for next cast)
                fish_btn = self._anchors.get("fishing_button")
                if fish_btn:
                    self._input.move_to(fish_btn[0], fish_btn[1], jitter=False)
                    time.sleep(0.7)
                    self._input.click(fish_btn[0], fish_btn[1], jitter=False)
                    time.sleep(0.3)

        return events

    def prime_fishing_ui(self) -> list[dict[str, str]]:
        """Open/confirm fishing toolbar once (FishSol post-catch click, run at session start)."""
        events: list[dict[str, str]] = []
        fish_btn = self._anchors.get("fishing_button")
        if not fish_btn:
            return events
        self._input.move_to(fish_btn[0], fish_btn[1], jitter=False)
        time.sleep(0.15)
        self._input.click(fish_btn[0], fish_btn[1], jitter=False)
        time.sleep(0.75)
        events.append({"type": "fishing_prime", "message": "Primed fishing toolbar (rod UI) for casting."})
        return events

    def reset_session_state(self) -> None:
        """Clear minigame state when macro starts."""
        self._state = "idle"
        self._bar_color = None
        self._cast_start = 0.0

    def _normal_reel(self, region: ScreenRegion) -> None:
        """Normal reel: if bar color NOT found in region, click to keep in range.

        FishSol: PixelSearch, FoundX, FoundY, 513, 531, 856, 549, barColor, 5
        If ErrorLevel (not found) → MouseClick left
        """
        found = self._screen.find_color_in_region(region, self._bar_color, tolerance=5)
        if found is None:
            # Bar not visible in region — click at bar region center to reel
            cx = region.x + region.width // 2
            cy = region.y + region.height // 2
            self._input.click(cx, cy, jitter=False)
        time.sleep(0.01)

    def _advanced_reel(self, region: ScreenRegion) -> None:
        """Advanced reel: measure bar width, click only when bar is about to exit.

        FishSol: Find left edge of bar, scan right for bar width.
        If barWidth < threshold → click (bar nearly out of range).
        This gives higher catch rates by clicking just before the bar leaves.
        """
        left_pos = self._screen.find_color_in_region(region, self._bar_color, tolerance=5)
        if left_pos is None:
            # Bar not found at all — click at center
            cx = region.x + region.width // 2
            cy = region.y + region.height // 2
            self._input.click(cx, cy, jitter=False)
            time.sleep(0.01)
            return

        # Scan right from the found position to measure bar width
        bar_width = 1
        scan_x = left_pos[0] + 1
        right_bound = region.x + region.width
        while scan_x <= right_bound:
            pixel = self._screen.get_pixel_color(scan_x, left_pos[1])
            if pixel.matches(self._bar_color, tolerance=10):
                bar_width += 1
                scan_x += 1
            else:
                break

        if bar_width < self._advanced_threshold:
            # Bar is narrow — about to exit range, click now
            cx = region.x + region.width // 2
            cy = region.y + region.height // 2
            self._input.click(cx, cy, jitter=False)

        time.sleep(0.01)

    def _run_fishing_failsafe(self) -> None:
        """FishSol fishing failsafe: four screen clicks (coords per resolution in profile)."""
        keys = [f"fishing_failsafe_{i}" for i in range(1, 5)]
        if all(self._anchors.get(k) for k in keys):
            sequence = keys
        else:
            sequence = [
                "auto_unequip_confirm",
                "sell_close",
                "fishing_button",
                "fishing_cast_click",
            ]
        for key in sequence:
            pos = self._anchors.get(key)
            if pos:
                self._input.click(pos[0], pos[1])
                time.sleep(0.3)

    def snapshot(self) -> dict:
        return {
            "casts": self.stats.casts,
            "catches": self.stats.catches,
            "failsafes_triggered": self.stats.failsafes_triggered,
            "state": self._state,
            "advanced_detection": self._advanced_detection,
        }
