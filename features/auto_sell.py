from __future__ import annotations

import time
from dataclasses import dataclass

from core.input_controller import InputController


@dataclass
class AutoSellStats:
    sell_runs: int = 0
    items_sold: int = 0


class AutoSellService:
    name = "auto_sell"

    def __init__(self) -> None:
        self.stats = AutoSellStats()
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._anchors: dict[str, list[int]] = {}
        self._sell_all: bool = True
        self._pathing_mode: str = "vip"
        self._azerty: bool = False
        self._fishing_loop_count: int = 15
        self._pathing_failsafe_time: float = 61.0

    def configure(
        self,
        anchors: dict[str, list[int]],
        sell_all: bool = True,
        pathing_mode: str = "vip",
        azerty: bool = False,
        fishing_loop_count: int = 15,
        pathing_failsafe_time: float = 61.0,
    ) -> None:
        self._anchors = anchors
        self._sell_all = sell_all
        self._pathing_mode = pathing_mode
        self._azerty = azerty
        self._fishing_loop_count = max(1, int(fishing_loop_count))
        self._pathing_failsafe_time = float(pathing_failsafe_time)

    def _click_anchor(self, key: str, delay: float = 0.2) -> bool:
        pos = self._anchors.get(key)
        if not pos:
            return False
        self._input.move_to(pos[0], pos[1], jitter=False)
        time.sleep(0.08)
        self._input.click(pos[0], pos[1], jitter=False)
        time.sleep(delay)
        return True

    def _reset_character(self) -> None:
        # FishSol reset flow
        self._input.send_key("esc", hold_ms=160)
        time.sleep(1.05)
        self._input.send_key("r", hold_ms=160)
        time.sleep(1.05)
        self._input.send_key("enter", hold_ms=160)
        time.sleep(3.2)

    def run_sell_cycle(self) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        self.stats.sell_runs += 1
        events.append({"type": "auto_sell_start", "message": "Starting auto-sell pathing..."})

        # Teleport flow from FishSol sequence
        self._reset_character()
        self._click_anchor("teleport_menu", delay=0.22)
        self._click_anchor("teleport_npc", delay=0.22)

        t = self._anchors.get("teleport_npc")
        if t:
            self._input.scroll(t[0], t[1], 80, "up")
            time.sleep(0.4)
            self._input.scroll(t[0], t[1], 45, "down")
            time.sleep(0.25)

        # Sell pane
        if self._click_anchor("sell_menu_item", delay=0.1):
            self._input.click(*self._anchors["sell_menu_item"], jitter=False)
            time.sleep(0.2)
        self._click_anchor("sell_confirm", delay=0.4)

        sold = 0
        pick = "sell_all_button" if self._sell_all else "sell_single_button"
        for _ in range(self._fishing_loop_count):
            if not self._click_anchor("sell_item_list", delay=0.15):
                break
            self._click_anchor(pick, delay=0.2)
            self._click_anchor("sell_scroll_item", delay=0.5)
            sold += 1
            w = self._anchors.get("sell_white_check")
            if not w:
                continue
            # if list turns non-white we reached end
            from core.screen_reader import PixelColor, ScreenReader, ScreenRegion

            sr = ScreenReader()
            region = ScreenRegion(w[0], w[1], w[2] - w[0], w[3] - w[1])
            if sr.find_color_in_region(region, PixelColor(255, 255, 255), tolerance=3) is None:
                break

        self.stats.items_sold += sold
        self._click_anchor("sell_close", delay=0.2)
        events.append({"type": "auto_sell_done", "message": f"Auto-sell complete ({sold} item steps)."})
        return events

    def snapshot(self) -> dict:
        return {
            "sell_runs": self.stats.sell_runs,
            "items_sold": self.stats.items_sold,
            "sell_all": self._sell_all,
            "pathing_mode": self._pathing_mode,
        }
