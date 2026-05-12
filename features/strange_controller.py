"""Strange Controller and Biome Randomizer — uses items on timed intervals.

Replicates FishSol-Macro RunStrangeController() and RunBiomeRandomizer()
with exact pixel search, clipboard paste, and resolution-specific coordinates.
"""
from __future__ import annotations

import time
from core.input_controller import InputController
from core.screen_reader import PixelColor, ScreenReader, ScreenRegion


# FishSol pixel colors for item detection
SC_CONFIRM_PIXEL = PixelColor(0x45, 0x7D, 0xFF)   # 0x457dff — Strange Controller confirm button
BR_CONFIRM_PIXEL_1080 = PixelColor(0x45, 0x7D, 0xFF)  # same blue
BR_CONFIRM_PIXEL_768 = PixelColor(0x8B, 0x8B, 0x8B)   # 0x8b8b8b — 768p variant


class StrangeControllerService:
    """Uses Strange Controller every 21 minutes (1260000ms).

    FishSol: Opens inventory → searches "Strange Controller" → clicks result →
             waits for confirm pixel → clicks confirm → closes inventory.
    """
    name = "strange_controller"

    # FishSol defaults (ms → seconds)
    DEFAULT_TIME = 0.0           # first run immediately (strangeControllerTime := 0)
    DEFAULT_INTERVAL = 1260.0    # 21 minutes (1260000ms)

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._screen = ScreenReader()
        self._anchors: dict[str, list[int]] = {}
        self._resolution: str = "1080p"
        self._interval: float = self.DEFAULT_INTERVAL
        self._first_time: float = self.DEFAULT_TIME
        self._last_run: float = 0.0
        self._webhook_enabled: bool = False
        self._uses: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        resolution: str = "1080p",
        interval: float = DEFAULT_INTERVAL,
        first_time: float = DEFAULT_TIME,
        webhook_enabled: bool = False,
    ) -> None:
        self._anchors = anchors
        self._resolution = resolution
        self._interval = interval
        self._first_time = first_time
        self._webhook_enabled = webhook_enabled

    def should_run(self, elapsed: float) -> bool:
        if self._last_run == 0 and elapsed >= self._first_time:
            return True
        if self._last_run > 0 and (elapsed - self._last_run) >= self._interval:
            return True
        return False

    def run(self) -> list[dict[str, str]]:
        """Execute Strange Controller use sequence."""
        events: list[dict[str, str]] = []
        events.append({"type": "strange_controller_start", "message": "Using Strange Controller"})

        if self._resolution == "1080p":
            self._run_1080p()
        elif self._resolution == "1440p":
            self._run_1440p()
        elif self._resolution == "1366x768":
            self._run_768p()

        self._uses += 1
        events.append({"type": "strange_controller_used", "message": "Strange Controller was used"})
        return events

    def set_last_run(self, elapsed: float) -> None:
        self._last_run = elapsed

    def _run_1080p(self) -> None:
        """FishSol 1080p: MouseMove 46,520 → click → 1279,342 → click → 1104,368 → click
        Clipboard "Strange Controller" → ^v → 848,479 → click
        Loop PixelSearch 491,711,749,723, 0x457dff,3 → if found break, else retry
        → 682,578 → click → 1413,297 → click
        """
        time.sleep(0.3)
        # Open inventory
        self._input.move_to(46, 520, jitter=False)
        time.sleep(0.3)
        self._input.click(46, 520, jitter=False)
        time.sleep(0.3)
        # Click search box
        self._input.move_to(1279, 342, jitter=False)
        time.sleep(0.3)
        self._input.click(1279, 342, jitter=False)
        time.sleep(0.3)
        # Click search input field
        self._input.move_to(1104, 368, jitter=False)
        time.sleep(0.3)
        self._input.click(1104, 368, jitter=False)
        time.sleep(0.3)
        # Type search term
        self._input.type_text("Strange Controller")
        time.sleep(0.3)
        # Click search result
        self._input.move_to(848, 479, jitter=False)
        time.sleep(0.3)
        self._input.click(848, 479, jitter=False)
        time.sleep(0.3)
        # Wait for confirm button pixel (0x457dff in region 491,711 to 749,723)
        for _ in range(20):
            region = ScreenRegion(x=491, y=711, width=258, height=12)
            found = self._screen.find_color_in_region(region, SC_CONFIRM_PIXEL, tolerance=3)
            if found is not None:
                break
            # Retry: click search again then result
            self._input.move_to(1279, 342, jitter=False)
            time.sleep(0.3)
            self._input.click(1279, 342, jitter=False)
            time.sleep(0.3)
            self._input.move_to(848, 479, jitter=False)
            time.sleep(0.3)
            self._input.click(848, 479, jitter=False)
            time.sleep(0.3)
        # Click confirm
        self._input.move_to(682, 578, jitter=False)
        time.sleep(0.3)
        self._input.click(682, 578, jitter=False)
        time.sleep(0.3)
        # Close inventory
        self._input.move_to(1413, 297, jitter=False)
        time.sleep(0.3)
        self._input.click(1413, 297, jitter=False)
        time.sleep(0.3)

    def _run_1440p(self) -> None:
        """FishSol 1440p: MouseMove 52,693 → click → 1704,452 → click → 1473,489 → click
        Clipboard "Strange Controller" → ^v → 1144,643 → click
        Loop PixelSearch 655,916,914,929, 0x457dff,3 → if found break
        → 920,774 → click → 1896,403 → click
        """
        time.sleep(0.3)
        self._input.move_to(52, 693, jitter=False)
        time.sleep(0.3)
        self._input.click(52, 693, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1704, 452, jitter=False)
        time.sleep(0.3)
        self._input.click(1704, 452, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1473, 489, jitter=False)
        time.sleep(0.3)
        self._input.click(1473, 489, jitter=False)
        time.sleep(0.3)
        self._input.type_text("Strange Controller")
        time.sleep(0.3)
        self._input.move_to(1144, 643, jitter=False)
        time.sleep(0.3)
        self._input.click(1144, 643, jitter=False)
        time.sleep(0.3)
        for _ in range(20):
            region = ScreenRegion(x=655, y=916, width=259, height=13)
            found = self._screen.find_color_in_region(region, SC_CONFIRM_PIXEL, tolerance=3)
            if found is not None:
                break
            self._input.move_to(1704, 452, jitter=False)
            time.sleep(0.3)
            self._input.click(1704, 452, jitter=False)
            time.sleep(0.3)
            self._input.move_to(1144, 643, jitter=False)
            time.sleep(0.3)
            self._input.click(1144, 643, jitter=False)
            time.sleep(0.3)
        self._input.move_to(920, 774, jitter=False)
        time.sleep(0.3)
        self._input.click(920, 774, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1896, 403, jitter=False)
        time.sleep(0.3)
        self._input.click(1896, 403, jitter=False)
        time.sleep(0.3)

    def _run_768p(self) -> None:
        """FishSol 1366x768: MouseMove 42,376 → click → 911,242 → click → 785,262 → click
        Clipboard "Strange Controller" → ^v → 616,347 → click
        Loop PixelSearch 427,518,474,530, 0x457dff,3 → if found break
        → 486,413 → click → 1017,214 → click
        """
        time.sleep(0.3)
        self._input.move_to(42, 376, jitter=False)
        time.sleep(0.3)
        self._input.click(42, 376, jitter=False)
        time.sleep(0.3)
        self._input.move_to(911, 242, jitter=False)
        time.sleep(0.3)
        self._input.click(911, 242, jitter=False)
        time.sleep(0.3)
        self._input.move_to(785, 262, jitter=False)
        time.sleep(0.3)
        self._input.click(785, 262, jitter=False)
        time.sleep(0.3)
        self._input.type_text("Strange Controller")
        time.sleep(0.3)
        self._input.move_to(616, 347, jitter=False)
        time.sleep(0.3)
        self._input.click(616, 347, jitter=False)
        time.sleep(0.3)
        for _ in range(20):
            region = ScreenRegion(x=427, y=518, width=47, height=12)
            found = self._screen.find_color_in_region(region, SC_CONFIRM_PIXEL, tolerance=3)
            if found is not None:
                break
            self._input.move_to(911, 242, jitter=False)
            time.sleep(0.3)
            self._input.click(911, 242, jitter=False)
            time.sleep(0.3)
            self._input.move_to(616, 347, jitter=False)
            time.sleep(0.3)
            self._input.click(616, 347, jitter=False)
            time.sleep(0.3)
        self._input.move_to(486, 413, jitter=False)
        time.sleep(0.3)
        self._input.click(486, 413, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1017, 214, jitter=False)
        time.sleep(0.3)
        self._input.click(1017, 214, jitter=False)
        time.sleep(0.3)

    def snapshot(self) -> dict:
        return {
            "uses": self._uses,
            "last_run": self._last_run,
            "interval": self._interval,
        }


class BiomeRandomizerService:
    """Uses Biome Randomizer every 21 minutes (after 6 min first run).

    FishSol: Same UI flow as Strange Controller but searches "Biome Randomizer"
    and uses slightly different pixel search regions.
    """
    name = "biome_randomizer"

    # FishSol defaults (ms → seconds)
    DEFAULT_TIME = 360.0          # 6 minutes first run (360000ms)
    DEFAULT_INTERVAL = 1260.0    # 21 minutes (1260000ms)

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._screen = ScreenReader()
        self._anchors: dict[str, list[int]] = {}
        self._resolution: str = "1080p"
        self._interval: float = self.DEFAULT_INTERVAL
        self._first_time: float = self.DEFAULT_TIME
        self._last_run: float = 0.0
        self._webhook_enabled: bool = False
        self._uses: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        resolution: str = "1080p",
        interval: float = DEFAULT_INTERVAL,
        first_time: float = DEFAULT_TIME,
        webhook_enabled: bool = False,
    ) -> None:
        self._anchors = anchors
        self._resolution = resolution
        self._interval = interval
        self._first_time = first_time
        self._webhook_enabled = webhook_enabled

    def should_run(self, elapsed: float) -> bool:
        if self._last_run == 0 and elapsed >= self._first_time:
            return True
        if self._last_run > 0 and (elapsed - self._last_run) >= self._interval:
            return True
        return False

    def run(self) -> list[dict[str, str]]:
        """Execute Biome Randomizer use sequence."""
        events: list[dict[str, str]] = []
        events.append({"type": "biome_randomizer_start", "message": "Using Biome Randomizer"})

        if self._resolution == "1080p":
            self._run_1080p()
        elif self._resolution == "1440p":
            self._run_1440p()
        elif self._resolution == "1366x768":
            self._run_768p()

        self._uses += 1
        events.append({"type": "biome_randomizer_used", "message": "Biome Randomizer was used"})
        return events

    def set_last_run(self, elapsed: float) -> None:
        self._last_run = elapsed

    def _run_1080p(self) -> None:
        """FishSol 1080p: Same inventory open as SC but search "Biome Randomizer"
        PixelSearch 491,727,748,739, 0x457dff,3 → confirm → close
        """
        time.sleep(0.3)
        self._input.move_to(46, 520, jitter=False)
        time.sleep(0.3)
        self._input.click(46, 520, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1279, 342, jitter=False)
        time.sleep(0.3)
        self._input.click(1279, 342, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1104, 368, jitter=False)
        time.sleep(0.3)
        self._input.click(1104, 368, jitter=False)
        time.sleep(0.3)
        self._input.type_text("Biome Randomizer")
        time.sleep(0.3)
        self._input.move_to(848, 479, jitter=False)
        time.sleep(0.3)
        self._input.click(848, 479, jitter=False)
        time.sleep(0.3)
        # Note: slightly different Y region than SC (727-739 vs 711-723)
        for _ in range(20):
            region = ScreenRegion(x=491, y=727, width=257, height=12)
            found = self._screen.find_color_in_region(region, SC_CONFIRM_PIXEL, tolerance=3)
            if found is not None:
                break
            self._input.move_to(1279, 342, jitter=False)
            time.sleep(0.3)
            self._input.click(1279, 342, jitter=False)
            time.sleep(0.3)
            self._input.move_to(848, 479, jitter=False)
            time.sleep(0.3)
            self._input.click(848, 479, jitter=False)
            time.sleep(0.3)
        self._input.move_to(682, 578, jitter=False)
        time.sleep(0.3)
        self._input.click(682, 578, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1413, 297, jitter=False)
        time.sleep(0.3)
        self._input.click(1413, 297, jitter=False)
        time.sleep(0.3)

    def _run_1440p(self) -> None:
        """FishSol 1440p: Same as SC 1440p but search "Biome Randomizer"
        PixelSearch 755,916,913,928, 0x457dff,3
        """
        time.sleep(0.3)
        self._input.move_to(52, 693, jitter=False)
        time.sleep(0.3)
        self._input.click(52, 693, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1704, 452, jitter=False)
        time.sleep(0.3)
        self._input.click(1704, 452, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1473, 489, jitter=False)
        time.sleep(0.3)
        self._input.click(1473, 489, jitter=False)
        time.sleep(0.3)
        self._input.type_text("Biome Randomizer")
        time.sleep(0.3)
        self._input.move_to(1144, 643, jitter=False)
        time.sleep(0.3)
        self._input.click(1144, 643, jitter=False)
        time.sleep(0.3)
        for _ in range(20):
            region = ScreenRegion(x=755, y=916, width=158, height=12)
            found = self._screen.find_color_in_region(region, SC_CONFIRM_PIXEL, tolerance=3)
            if found is not None:
                break
            self._input.move_to(1704, 452, jitter=False)
            time.sleep(0.3)
            self._input.click(1704, 452, jitter=False)
            time.sleep(0.3)
            self._input.move_to(1144, 643, jitter=False)
            time.sleep(0.3)
            self._input.click(1144, 643, jitter=False)
            time.sleep(0.3)
        self._input.move_to(920, 774, jitter=False)
        time.sleep(0.3)
        self._input.click(920, 774, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1896, 403, jitter=False)
        time.sleep(0.3)
        self._input.click(1896, 403, jitter=False)
        time.sleep(0.3)

    def _run_768p(self) -> None:
        """FishSol 1366x768: Same as SC 768p but search "Biome Randomizer"
        PixelSearch 433,518,480,530, 0x8b8b8b,3 (different color than SC!)
        """
        time.sleep(0.3)
        self._input.move_to(42, 376, jitter=False)
        time.sleep(0.3)
        self._input.click(42, 376, jitter=False)
        time.sleep(0.3)
        self._input.move_to(911, 242, jitter=False)
        time.sleep(0.3)
        self._input.click(911, 242, jitter=False)
        time.sleep(0.3)
        self._input.move_to(785, 262, jitter=False)
        time.sleep(0.3)
        self._input.click(785, 262, jitter=False)
        time.sleep(0.3)
        self._input.type_text("Biome Randomizer")
        time.sleep(0.3)
        self._input.move_to(616, 347, jitter=False)
        time.sleep(0.3)
        self._input.click(616, 347, jitter=False)
        time.sleep(0.3)
        # Note: 768p uses 0x8b8b8b instead of 0x457dff for BR
        for _ in range(20):
            region = ScreenRegion(x=433, y=518, width=47, height=12)
            found = self._screen.find_color_in_region(region, BR_CONFIRM_PIXEL_768, tolerance=3)
            if found is not None:
                break
            self._input.move_to(911, 242, jitter=False)
            time.sleep(0.3)
            self._input.click(911, 242, jitter=False)
            time.sleep(0.3)
            self._input.move_to(616, 347, jitter=False)
            time.sleep(0.3)
            self._input.click(616, 347, jitter=False)
            time.sleep(0.3)
        self._input.move_to(486, 413, jitter=False)
        time.sleep(0.3)
        self._input.click(486, 413, jitter=False)
        time.sleep(0.3)
        self._input.move_to(1017, 214, jitter=False)
        time.sleep(0.3)
        self._input.click(1017, 214, jitter=False)
        time.sleep(0.3)

    def snapshot(self) -> dict:
        return {
            "uses": self._uses,
            "last_run": self._last_run,
            "interval": self._interval,
        }
