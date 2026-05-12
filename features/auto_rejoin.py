"""Auto-rejoin failsafe — kills Roblox and rejoins via private server link.

Replicates FishSol-Macro auto-rejoin logic:
  1. Process Close RobloxPlayerBeta.exe
  2. Run roblox:// navigation link with private server code
  3. Click skip button, wait, click start button
  4. Pixel-search for green start pixel (0x82ff95)
"""
from __future__ import annotations

import subprocess
import time
from core.input_controller import InputController
from core.screen_reader import PixelColor, ScreenReader, ScreenRegion


# FishSol: PixelSearch for green start button 0x82ff95
GREEN_START_PIXEL = PixelColor(0x82, 0xFF, 0x95)


class AutoRejoinService:
    name = "auto_rejoin"

    # FishSol default: 320 seconds (autoRejoinFailsafeTime := 320)
    DEFAULT_TIMEOUT = 320.0

    def __init__(self) -> None:
        self._input = InputController(jitter_px=2, delay_ms=30)
        self._screen = ScreenReader()
        self._anchors: dict[str, list[int]] = {}
        self._resolution: str = "1080p"
        self._timeout: float = self.DEFAULT_TIMEOUT
        self._private_server_link: str = ""
        self._private_server_code: str = ""
        self._rejoins: int = 0

    def configure(
        self,
        anchors: dict[str, list[int]],
        resolution: str = "1080p",
        timeout: float = DEFAULT_TIMEOUT,
        private_server_link: str = "",
    ) -> None:
        self._anchors = anchors
        self._resolution = resolution
        self._timeout = timeout
        self._private_server_link = private_server_link
        # Extract code from link (FishSol: RegExMatch code=([^&]+))
        if "code=" in private_server_link:
            start = private_server_link.index("code=") + 5
            end = private_server_link.find("&", start)
            self._private_server_code = private_server_link[start:end] if end != -1 else private_server_link[start:]
        else:
            self._private_server_code = ""

    @property
    def has_link(self) -> bool:
        return bool(self._private_server_link.strip())

    def should_rejoin(self, global_failsafe_elapsed: float) -> bool:
        """Check if auto-rejoin should trigger."""
        return (
            global_failsafe_elapsed > self._timeout
            and self.has_link
        )

    def run(self) -> list[dict[str, str]]:
        """Execute auto-rejoin sequence. Returns events."""
        events: list[dict[str, str]] = []
        events.append({"type": "auto_rejoin_start", "message": "Auto-rejoin failsafe triggered"})

        # Step 1: Kill Roblox (FishSol: Process Close RobloxPlayerBeta.exe)
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "RobloxPlayerBeta.exe"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass
        time.sleep(0.5)

        # Step 2: Open Roblox with private server link
        # FishSol: Run powershell Start-Process 'roblox://navigation/share_links?code=...&type=Server'
        if self._private_server_code:
            roblox_url = f"roblox://navigation/share_links?code={self._private_server_code}&type=Server"
        else:
            roblox_url = self._private_server_link

        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Start-Process '{roblox_url}'"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

        time.sleep(5.0)

        # Step 3: Activate Roblox window
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Find Roblox window and bring to foreground
            hwnd = user32.FindWindowW(None, "Roblox")
            if hwnd:
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(6.0)

        # Step 4: Click skip button (resolution-specific)
        if self._resolution == "1080p":
            self._input.move_to(960, 540, jitter=False)
            time.sleep(0.2)
            self._input.click(960, 540, jitter=False)
        elif self._resolution == "1440p":
            self._input.move_to(1280, 720, jitter=False)
            time.sleep(0.2)
            self._input.click(1280, 720, jitter=False)
        elif self._resolution == "1366x768":
            self._input.move_to(683, 384, jitter=False)
            time.sleep(0.2)
            self._input.click(683, 384, jitter=False)
        time.sleep(6.0)

        # Step 5: Wait for and click start button (pixel search for 0x82ff95)
        # FishSol: PixelSearch for green pixel in start button region
        start_pixel = self._anchors.get("rejoin_start_pixel")
        start_btn = self._anchors.get("rejoin_start_button")

        if start_pixel and len(start_pixel) >= 4:
            region = ScreenRegion(
                x=start_pixel[0], y=start_pixel[3],  # FishSol: y1>y2 in some cases
                width=abs(start_pixel[2] - start_pixel[0]),
                height=abs(start_pixel[1] - start_pixel[3]),
            )
            # Search for green pixel up to 30 seconds
            for _ in range(300):
                found = self._screen.find_color_in_region(region, GREEN_START_PIXEL, tolerance=5)
                if found is not None:
                    time.sleep(1.0)
                    if start_btn:
                        self._input.move_to(start_btn[0], start_btn[1], jitter=False)
                        time.sleep(0.35)
                        self._input.click(start_btn[0], start_btn[1], jitter=False)
                    break
                time.sleep(0.1)

        time.sleep(3.0)
        self._rejoins += 1
        events.append({"type": "auto_rejoin_done", "message": "Auto-rejoin complete"})
        return events

    def snapshot(self) -> dict:
        return {
            "rejoins": self._rejoins,
            "timeout": self._timeout,
            "has_link": self.has_link,
        }
