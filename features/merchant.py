from __future__ import annotations

import time
from dataclasses import dataclass

from core.input_controller import InputController
from core.screen_reader import PixelColor, ScreenReader


@dataclass
class MerchantStats:
    encounters: int = 0
    purchases: int = 0
    crafter_detected: int = 0


# FishSol merchant click colors
# Crafter pixel: 0x6eb4ff (blue) at crafter_pixel anchor
CRAFTER_PIXEL = PixelColor(0x6E, 0xB4, 0xFF)


class MerchantService:
    name = "merchant"

    def __init__(self) -> None:
        self.stats = MerchantStats()
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._screen = ScreenReader()
        self._anchors: dict[str, list[int]] = {}
        self._last_merchant_click: float = 0.0
        self._merchant_click_interval: float = 5.0  # FishSol: SetTimer MerchantClick, 5000
        self._last_crafter_check: float = 0.0
        self._crafter_check_interval: float = 2.0
        self._auto_crafter: bool = False

    def configure(
        self,
        anchors: dict[str, list[int]],
        auto_crafter: bool = False,
    ) -> None:
        self._anchors = anchors
        self._auto_crafter = auto_crafter

    def tick(self, active: bool) -> list[dict[str, str]]:
        if not active or not self._anchors:
            return []

        events: list[dict[str, str]] = []
        now = time.time()

        # Merchant click — FishSol: SetTimer MerchantClick2, 5000
        # Clicks the merchant NPC position every 5 seconds during pathing
        if now - self._last_merchant_click >= self._merchant_click_interval:
            self._last_merchant_click = now
            merchant_pos = self._anchors.get("merchant_click")
            if merchant_pos:
                self._input.click(merchant_pos[0], merchant_pos[1], clicks=3)
                self.stats.encounters += 1
                events.append({
                    "type": "merchant_click",
                    "message": "Merchant click (auto-interact).",
                })

        # Crafter detection — FishSol: PixelSearch 2203,959, 0x6eb4ff, 3
        if self._auto_crafter and now - self._last_crafter_check >= self._crafter_check_interval:
            self._last_crafter_check = now
            crafter_pos = self._anchors.get("crafter_pixel")
            if crafter_pos:
                if self._screen.pixel_matches(
                    crafter_pos[0], crafter_pos[1], CRAFTER_PIXEL, tolerance=3
                ):
                    self.stats.crafter_detected += 1
                    # Click the crafter
                    self._input.click(crafter_pos[0], crafter_pos[1])
                    events.append({
                        "type": "crafter_detected",
                        "message": "Auto-crafter detected and clicked!",
                    })

        return events

    def snapshot(self) -> dict:
        return {
            "encounters": self.stats.encounters,
            "purchases": self.stats.purchases,
            "crafter_detected": self.stats.crafter_detected,
            "auto_crafter": self._auto_crafter,
        }
