"""Auto-unequip and auto-close-chat — pre-sell cleanup actions.

Replicates FishSol-Macro:
  - autoUnequip: Opens inventory → clicks aura slot → unequips → closes
  - autoCloseChat: Presses / → clicks chat close button
"""
from __future__ import annotations

import time
from core.input_controller import InputController


class AutoUnequipService:
    """Unequips the currently rolled aura to prevent lag.

    FishSol 1080p: MouseMove 45,412 → click → 830,441 → click → 634,638 → click
                   → 634,638 → click (double click confirm) → 1425,303 → click (close)
    FishSol 1440p: MouseMove 41,538 → click → 1089,575 → click → 835,845 → click
                   → 835,845 → click → 1882,395 → click
    FishSol 768p:  MouseMove 26,292 → click → 580,312 → click → 449,452 → click
                   → 449,452 → click → 1016,218 → click
    """
    name = "auto_unequip"

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._anchors: dict[str, list[int]] = {}
        self._resolution: str = "1080p"
        self._enabled: bool = False
        self._unequips: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        resolution: str = "1080p",
        enabled: bool = False,
    ) -> None:
        self._anchors = anchors
        self._resolution = resolution
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def run(self) -> list[dict[str, str]]:
        """Execute auto-unequip sequence."""
        if not self._enabled:
            return []

        events: list[dict[str, str]] = []

        # Use anchor points for resolution-independent approach
        menu_pos = self._anchors.get("auto_unequip_menu")
        item_pos = self._anchors.get("auto_unequip_item")
        confirm_pos = self._anchors.get("auto_unequip_confirm")
        close_pos = self._anchors.get("auto_unequip_close")

        if not all([menu_pos, item_pos, confirm_pos, close_pos]):
            # Fallback to hardcoded resolution-specific coordinates from FishSol
            self._run_hardcoded()
        else:
            # Click inventory menu
            self._input.move_to(menu_pos[0], menu_pos[1], jitter=False)
            time.sleep(0.3)
            self._input.click(menu_pos[0], menu_pos[1], jitter=False)
            time.sleep(0.3)

            # Click aura item
            self._input.move_to(item_pos[0], item_pos[1], jitter=False)
            time.sleep(0.3)
            self._input.click(item_pos[0], item_pos[1], jitter=False)
            time.sleep(0.3)

            # Click confirm (double click — FishSol has two clicks with 1200ms gap)
            self._input.move_to(confirm_pos[0], confirm_pos[1], jitter=False)
            time.sleep(0.3)
            self._input.click(confirm_pos[0], confirm_pos[1], jitter=False)
            time.sleep(1.2)
            self._input.click(confirm_pos[0], confirm_pos[1], jitter=False)
            time.sleep(0.3)

            # Close inventory
            self._input.move_to(close_pos[0], close_pos[1], jitter=False)
            time.sleep(0.3)
            self._input.click(close_pos[0], close_pos[1], jitter=False)
            time.sleep(0.3)

        self._unequips += 1
        events.append({"type": "auto_unequip", "message": "Unequipped aura"})
        return events

    def _run_hardcoded(self) -> None:
        """Fallback using exact FishSol coordinates per resolution."""
        if self._resolution == "1080p":
            self._input.move_to(45, 412, jitter=False)
            time.sleep(0.3)
            self._input.click(45, 412, jitter=False)
            time.sleep(0.3)
            self._input.move_to(830, 441, jitter=False)
            time.sleep(0.3)
            self._input.click(830, 441, jitter=False)
            time.sleep(0.3)
            self._input.move_to(634, 638, jitter=False)
            time.sleep(0.3)
            self._input.click(634, 638, jitter=False)
            time.sleep(1.2)
            self._input.click(634, 638, jitter=False)
            time.sleep(0.3)
            self._input.move_to(1425, 303, jitter=False)
            time.sleep(0.3)
            self._input.click(1425, 303, jitter=False)
            time.sleep(0.3)
        elif self._resolution == "1440p":
            self._input.move_to(41, 538, jitter=False)
            time.sleep(0.3)
            self._input.click(41, 538, jitter=False)
            time.sleep(0.3)
            self._input.move_to(1089, 575, jitter=False)
            time.sleep(0.3)
            self._input.click(1089, 575, jitter=False)
            time.sleep(0.3)
            self._input.move_to(835, 845, jitter=False)
            time.sleep(0.3)
            self._input.click(835, 845, jitter=False)
            time.sleep(1.2)
            self._input.click(835, 845, jitter=False)
            time.sleep(0.3)
            self._input.move_to(1882, 395, jitter=False)
            time.sleep(0.3)
            self._input.click(1882, 395, jitter=False)
            time.sleep(0.3)
        elif self._resolution == "1366x768":
            self._input.move_to(26, 292, jitter=False)
            time.sleep(0.3)
            self._input.click(26, 292, jitter=False)
            time.sleep(0.3)
            self._input.move_to(580, 312, jitter=False)
            time.sleep(0.3)
            self._input.click(580, 312, jitter=False)
            time.sleep(0.3)
            self._input.move_to(449, 452, jitter=False)
            time.sleep(0.3)
            self._input.click(449, 452, jitter=False)
            time.sleep(1.2)
            self._input.click(449, 452, jitter=False)
            time.sleep(0.3)
            self._input.move_to(1016, 218, jitter=False)
            time.sleep(0.3)
            self._input.click(1016, 218, jitter=False)
            time.sleep(0.3)

    def snapshot(self) -> dict:
        return {
            "enabled": self._enabled,
            "unequips": self._unequips,
        }


class AutoCloseChatService:
    """Closes chat to prevent the macro from getting stuck.

    FishSol: Send {/} → MouseMove chat_close → MouseClick Left
    The chat_close anchor is resolution-specific.
    """
    name = "auto_close_chat"

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._anchors: dict[str, list[int]] = {}
        self._enabled: bool = False
        self._closes: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        enabled: bool = False,
    ) -> None:
        self._anchors = anchors
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def run(self) -> list[dict[str, str]]:
        """Execute auto-close-chat sequence."""
        if not self._enabled:
            return []

        events: list[dict[str, str]] = []

        # FishSol: Send {/} to open chat, then click close button
        time.sleep(0.3)
        self._input.send_key("/")
        time.sleep(0.3)

        chat_close = self._anchors.get("chat_close")
        if chat_close:
            self._input.move_to(chat_close[0], chat_close[1], jitter=False)
            time.sleep(0.3)
            self._input.click(chat_close[0], chat_close[1], jitter=False)
            time.sleep(0.3)

        self._closes += 1
        events.append({"type": "auto_close_chat", "message": "Closed chat"})
        return events

    def snapshot(self) -> dict:
        return {
            "enabled": self._enabled,
            "closes": self._closes,
        }
