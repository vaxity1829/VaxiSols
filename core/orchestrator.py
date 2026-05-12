from __future__ import annotations

import ctypes
import json
import threading
import time
from pathlib import Path
from typing import Any

from core.roblox_window import RobloxWindow, RobloxWindowManager
from features.anti_afk import AntiAfkService
from features.auto_rejoin import AutoRejoinService
from features.auto_sell import AutoSellService
from features.auto_unequip import AutoCloseChatService, AutoUnequipService
from features.biome_aura import BiomeAuraService
from features.easter import EasterService
from features.fishing import FishingService
from features.merchant import MerchantService
from features.snowman import SnowmanService
from features.strange_controller import BiomeRandomizerService, StrangeControllerService
from integrations.webhooks import WebhookService
from plugins.loader import PluginLoader
from reporting.session_report import SessionReport


def _map_profile_anchors_to_screen(
    hwnd: int,
    profile: dict[str, list[int]],
    ref_w: int,
    ref_h: int,
) -> tuple[dict[str, list[int]], float, float]:
    """Scale profile coords from reference client size to actual client, then ClientToScreen.

    FishSol anchors are tuned for a specific client pixel size; Roblox's real client area
    often differs slightly (chrome, scaling, exclusive fullscreen), which misaligns clicks.
    """
    cw, ch = RobloxWindow.get_client_size(hwnd)
    sx = cw / float(ref_w) if ref_w > 0 else 1.0
    sy = ch / float(ref_h) if ref_h > 0 else 1.0
    out: dict[str, list[int]] = {}
    for k, v in profile.items():
        if len(v) == 2:
            cx = int(round(v[0] * sx))
            cy = int(round(v[1] * sy))
            sxp, syp = RobloxWindow.client_point_to_screen(hwnd, cx, cy)
            out[k] = [sxp, syp]
        elif len(v) == 4:
            x1 = int(round(v[0] * sx))
            y1 = int(round(v[1] * sy))
            x2 = int(round(v[2] * sx))
            y2 = int(round(v[3] * sy))
            ax, ay = RobloxWindow.client_point_to_screen(hwnd, x1, y1)
            bx, by = RobloxWindow.client_point_to_screen(hwnd, x2, y2)
            out[k] = [ax, ay, bx, by]
        else:
            out[k] = list(v)
    return out, sx, sy


class MacroOrchestrator:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self.state = "stopped"
        self.last_error: str | None = None

        # Window manager for focusing Roblox
        self._window_mgr = RobloxWindowManager()

        # Feature enable flags — matches FishSol GUI toggles
        self.enabled_features: dict[str, bool] = {
            "fishing": True,
            "auto_sell": True,
            "anti_afk": True,
            "biome_detector": True,
            "strange_controller": False,
            "biome_randomizer": False,
            "snowman": False,
            "easter": False,
            "auto_unequip": False,
            "auto_close_chat": False,
            "auto_rejoin": True,
            "auto_crafter": False,
        }

        # Services
        self.fishing = FishingService()
        self.auto_sell = AutoSellService()
        self.biome_aura = BiomeAuraService()
        self.merchant = MerchantService()
        self.anti_afk = AntiAfkService()
        self.snowman = SnowmanService()
        self.easter = EasterService()
        self.strange_controller = StrangeControllerService()
        self.biome_randomizer = BiomeRandomizerService()
        self.auto_rejoin = AutoRejoinService()
        self.auto_unequip = AutoUnequipService()
        self.auto_close_chat = AutoCloseChatService()

        self.webhooks = WebhookService()
        self.plugin_loader = PluginLoader(root_dir / "plugins")
        self.plugin_status = self.plugin_loader.discover()
        self.session = SessionReport()

        # Config loaded from resolution profiles (template = client-relative; _anchors =
        # translated to screen using Roblox client's top-left when the macro loop runs.)
        self._anchor_profile: dict[str, list[int]] = {}
        self._anchors: dict[str, list[int]] = {}
        self._profile_reference_size: tuple[int, int] = (1920, 1080)
        self._last_anchor_sync_key: tuple[int, int, int, int, int] | None = None
        self._alignment_info: dict[str, Any] = {}
        self._resolution: str = "1080p"

        # FishSol loop state
        self._start_tick: float = 0.0
        self._max_loop_count: int = 15       # FishSol: maxLoopCount
        self._sell_every_casts: int = 15     # sell after N catches
        self._casts_since_sell: int = 0
        self._cycle_count: int = 0
        self._restart_pathing: bool = False
        self._is_pathing: bool = False

        # Failsafe timers
        self._global_failsafe_timer: float = 0.0
        self._auto_rejoin_failsafe_time: float = 320.0   # FishSol: 320s
        self._fishing_failsafe_time: float = 31.0         # FishSol: 31s
        self._pathing_failsafe_time: float = 61.0         # FishSol: 61s

        # ClearUI / PressE timers
        self._last_clear_ui: float = 0.0
        self._clear_ui_interval: float = 15.0   # FishSol: SetTimer ClearUI, 15000
        self._last_do_e: float = 0.0
        self._last_refocus: float = 0.0
        self._last_game_focus: float = 0.0
        self._do_e_interval: float = 0.1         # FishSol: SetTimer PressE, 100

        # Fishing session startup (reset / UI / camera before first cast)
        self._fishing_reset_on_start: bool = True
        self._fishing_clear_ui_on_start: bool = True
        self._fishing_scroll_camera_on_start: bool = True
        self._fishing_prime_ui_on_start: bool = True
        self._fishing_scroll_notches: int = 5
        self._run_pathing_before_fishing_start: bool = True

        # Webhook toggles (FishSol: failsafeWebhook, pathingWebhook, itemWebhook)
        self._failsafe_webhook: bool = False
        self._pathing_webhook: bool = False
        self._item_webhook: bool = False

        # Username for webhook messages
        self._username: str = ""

        # Long inventory/pathing (Strange Controller, Snowman, Easter, BR) must not steal
        # the first seconds of the session or interrupt active fishing/minigames.
        self._startup_grace_seconds: float = 60.0

        self.load_config()

    def load_config(self) -> None:
        cfg = self.root_dir / "config" / "default.json"
        if not cfg.exists():
            return
        # Retry up to 3 times — save_config may write the file concurrently
        data = None
        for _ in range(3):
            try:
                raw = cfg.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
                    break
            except (json.JSONDecodeError, OSError):
                time.sleep(0.1)
        if data is None:
            self.last_error = "config load failed: file empty or corrupt after retries"
            return
        try:
            self.enabled_features.update(data.get("features", {}))
            self.webhooks.update_urls(data.get("webhooks", {}).get("urls", []))

            # Load anchors from active resolution profile
            profile_id = data.get("active_resolution_profile", "")
            profiles_path = self.root_dir / "config" / "resolution_profiles.json"
            self._anchor_profile = {}
            if profiles_path.exists():
                try:
                    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    profiles = {}
                for p in profiles.get("profiles", []):
                    if p.get("id") == profile_id:
                        raw = p.get("anchor_points", {})
                        self._anchor_profile = {key: list(val) for key, val in raw.items()}
                        self._anchors = {key: list(val) for key, val in raw.items()}
                        self._last_anchor_sync_key = None
                        if "1440" in profile_id:
                            self._resolution = "1440p"
                        elif "768" in profile_id:
                            self._resolution = "1366x768"
                        else:
                            self._resolution = "1080p"
                        ref = p.get("reference_client")
                        if isinstance(ref, list) and len(ref) >= 2:
                            self._profile_reference_size = (int(ref[0]), int(ref[1]))
                        else:
                            self._profile_reference_size = self._get_target_resolution_size()
                        break

            if not self._anchor_profile:
                self._anchors = {}

            # Configure all services with anchors and settings
            self.fishing.configure(
                anchors=self._anchors,
                advanced_detection=data.get("advanced_fishing_detection", False),
                advanced_threshold=data.get("advanced_fishing_threshold", 25),
                fishing_failsafe_time=data.get("fishing_failsafe_time", 31.0),
            )
            self.auto_sell.configure(
                anchors=self._anchors,
                sell_all=data.get("sell_all", False),
                pathing_mode=data.get("pathing_mode", "vip"),
                azerty=data.get("azerty", False),
                fishing_loop_count=data.get("fishing_loop_count", 15),
                pathing_failsafe_time=data.get("pathing_failsafe_time", 61.0),
            )
            self.merchant.configure(
                anchors=self._anchors,
                auto_crafter=data.get("auto_crafter", False),
            )
            self.snowman.configure(
                anchors=self._anchors,
                pathing_mode=data.get("pathing_mode", "vip"),
                resolution=self._resolution,
                interval=data.get("snowman_interval", 7500.0),
                webhook_enabled=self.enabled_features.get("snowman", False),
            )
            self.easter.configure(
                anchors=self._anchors,
                pathing_mode=data.get("pathing_mode", "vip"),
                resolution=self._resolution,
                interval=data.get("easter_interval", 1800.0),
                webhook_enabled=self.enabled_features.get("easter", False),
                limited_pathing=data.get("limited_pathing", False),
                pause_auto_roll=data.get("pause_auto_roll", False),
            )
            self.strange_controller.configure(
                anchors=self._anchors,
                resolution=self._resolution,
                interval=data.get("strange_controller_interval", 1260.0),
                first_time=data.get("strange_controller_time", 0.0),
                webhook_enabled=self.enabled_features.get("strange_controller", False),
            )
            self.biome_randomizer.configure(
                anchors=self._anchors,
                resolution=self._resolution,
                interval=data.get("biome_randomizer_interval", 1260.0),
                first_time=data.get("biome_randomizer_time", 360.0),
                webhook_enabled=self.enabled_features.get("biome_randomizer", False),
            )
            self.auto_rejoin.configure(
                anchors=self._anchors,
                resolution=self._resolution,
                timeout=data.get("auto_rejoin_failsafe_time", 320.0),
                private_server_link=data.get("private_server_link", ""),
            )
            self.auto_unequip.configure(
                anchors=self._anchors,
                resolution=self._resolution,
                enabled=self.enabled_features.get("auto_unequip", False),
            )
            self.auto_close_chat.configure(
                anchors=self._anchors,
                enabled=self.enabled_features.get("auto_close_chat", False),
            )

            # Scalar settings
            self._max_loop_count = data.get("max_loop_count", 15)
            self._sell_every_casts = self._max_loop_count
            self._auto_rejoin_failsafe_time = data.get("auto_rejoin_failsafe_time", 320.0)
            self._fishing_failsafe_time = data.get("fishing_failsafe_time", 31.0)
            self._pathing_failsafe_time = data.get("pathing_failsafe_time", 61.0)
            self._failsafe_webhook = data.get("failsafe_webhook", False)
            self._pathing_webhook = data.get("pathing_webhook", False)
            self._item_webhook = data.get("item_webhook", False)
            self._username = data.get("username", "")
            self.biome_aura.configure(username=self._username or None)

            self._startup_grace_seconds = float(
                data.get("timed_feature_startup_grace_seconds", 60.0)
            )

            self._fishing_reset_on_start = bool(
                data.get("fishing_reset_character_on_start", True)
            )
            self._fishing_clear_ui_on_start = bool(data.get("fishing_clear_ui_on_start", True))
            self._fishing_scroll_camera_on_start = bool(
                data.get("fishing_scroll_camera_on_start", True)
            )
            self._fishing_prime_ui_on_start = bool(data.get("fishing_prime_ui_on_start", True))
            self._fishing_scroll_notches = max(
                0, min(24, int(data.get("fishing_camera_zoom_scroll_notches", 5)))
            )
            self._run_pathing_before_fishing_start = bool(
                data.get("run_pathing_before_fishing_start", True)
            )

        except Exception as exc:
            self.last_error = f"config load failed: {exc}"

    def _roblox_reset_character(self) -> None:
        """FishSol-style respawn: Esc → R → Enter (longer holds / gaps for Roblox menu)."""
        inp = self.fishing._input
        inp.send_key("esc", hold_ms=160)
        time.sleep(1.05)
        inp.send_key("r", hold_ms=160)
        time.sleep(1.05)
        inp.send_key("enter", hold_ms=160)
        time.sleep(3.2)

    def _run_fishing_startup_alignment(self, win: RobloxWindow) -> None:
        """Close menus, optionally reset, clear UI, zoom camera, prime rod toolbar (FishSol parity)."""
        if not self._anchors:
            self._handle_event({
                "type": "fishing_prep_skip",
                "message": "Fishing prep skipped: no anchors (check resolution profile).",
            })
            return

        hwnd = win.hwnd
        self._handle_event({
            "type": "fishing_prep_start",
            "message": "Fishing alignment: menus → optional reset → clear UI → camera → prime rod UI.",
        })

        inp = self.fishing._input
        inp.send_key("esc", hold_ms=140)
        time.sleep(0.55)
        inp.send_key("esc", hold_ms=140)
        time.sleep(0.55)

        if self._fishing_reset_on_start:
            self._handle_event({
                "type": "fishing_prep_reset",
                "message": "Resetting character (Esc → R → Enter). Walk back to your fishing spot if needed.",
            })
            self._roblox_reset_character()

        if self._fishing_clear_ui_on_start:
            cu = self._anchors.get("clear_ui_click")
            if cu:
                inp.move_to(cu[0], cu[1], jitter=False)
                time.sleep(0.15)
                inp.click(cu[0], cu[1], jitter=False)
                time.sleep(0.35)
                self._handle_event({
                    "type": "fishing_prep_clear_ui",
                    "message": "Clear UI click to reduce overlays.",
                })

        if self._fishing_scroll_camera_on_start and self._fishing_scroll_notches > 0:
            cx, cy = RobloxWindow.client_center_screen(hwnd)
            inp.move_to(cx, cy, jitter=False)
            time.sleep(0.12)
            n = min(24, self._fishing_scroll_notches)
            inp.scroll(cx, cy, clicks=n, direction="down")
            time.sleep(0.35)
            self._handle_event({
                "type": "fishing_prep_camera",
                "message": f"Camera: {n} scroll step(s) at client center (Roblox zoom).",
            })

        if self._fishing_prime_ui_on_start:
            for ev in self.fishing.prime_fishing_ui():
                self._handle_event(ev)
        else:
            self._handle_event({
                "type": "fishing_prep_prime_skipped",
                "message": "Rod UI prime disabled — open the fishing toolbar manually before casting.",
            })

    def _timed_inventory_safe(self, now: float) -> bool:
        """True when Strange Controller / Snowman / Easter / BR may run safely.

        Must not block waiting for a bite or the reel minigame. Checked *after*
        ``fishing.tick`` so Strange can run in the idle gap between catches without
        running before `start()` / first casts (startup grace prevents that).
        """
        if self._is_pathing:
            return False
        if self._start_tick and (now - self._start_tick) < self._startup_grace_seconds:
            return False
        if self.fishing._state in ("waiting_bite", "reeling"):
            return False
        return True

    def start(self) -> None:
        with self._lock:
            if self.state == "running":
                return
            if self._thread and self._thread.is_alive():
                self._pause_event.clear()
                self.state = "running"
                return

            self._stop_event.clear()
            self._pause_event.clear()
            self._start_tick = time.time()
            self._global_failsafe_timer = 0.0
            self._casts_since_sell = 0
            self._restart_pathing = False
            self._last_anchor_sync_key = None
            self.biome_aura.reset_session()
            self.session.begin()

            if self._anchor_profile:
                self._anchors = {
                    key: list(val) for key, val in self._anchor_profile.items()
                }
                self._publish_anchors_to_services()

            # Focus Roblox window before starting
            win = self._window_mgr.find_primary()
            if win:
                win.bring_to_foreground()
                time.sleep(0.5)
                self._maybe_sync_anchor_screen_offset()
                al = self._alignment_info
                cw, ch = (al.get("client_size") or [0, 0])[0:2]
                sc = al.get("scale") or [1.0, 1.0]
                self._handle_event({
                    "type": "window_focus",
                    "message": (
                        f"Roblox outer {win.rect.width}x{win.rect.height}; "
                        f"client {cw}x{ch} (ref {self._profile_reference_size[0]}x{self._profile_reference_size[1]}); "
                        f"scale {sc[0]:.3f}x{sc[1]:.3f}; anchors mapped for fishing/UI."
                    ),
                })
            else:
                self._handle_event({"type": "window_focus", "message": "WARNING: No Roblox window found! Macro will run but may not interact correctly."})

            self.fishing.reset_session_state()
            if win and self.enabled_features.get("fishing"):
                if (
                    self._run_pathing_before_fishing_start
                    and self.enabled_features.get("auto_sell")
                ):
                    self._handle_event({
                        "type": "startup_pathing",
                        "message": "Running FishSol-style sell/pathing once before first fishing cast.",
                    })
                    self._is_pathing = True
                    for event in self.auto_sell.run_sell_cycle():
                        self._handle_event(event)
                    self._is_pathing = False
                self._run_fishing_startup_alignment(win)

            self.state = "running"
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._handle_event({"type": "macro_start", "message": "Macro started"})

    def pause(self) -> None:
        with self._lock:
            if self.state == "running":
                self._pause_event.set()
                self.state = "paused"

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            self._pause_event.clear()
            self.state = "stopped"
            self.session.end()

    def set_feature_enabled(self, feature_name: str, enabled: bool) -> None:
        if feature_name in self.enabled_features:
            self.enabled_features[feature_name] = enabled
        # Sync to service objects
        if feature_name == "auto_unequip":
            self.auto_unequip.enabled = enabled
        elif feature_name == "auto_close_chat":
            self.auto_close_chat.enabled = enabled

    def _get_target_resolution_size(self) -> tuple[int, int]:
        """Get the expected window size for the active resolution profile."""
        size_map = {
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "1366x768": (1366, 768),
        }
        return size_map.get(self._resolution, (1920, 1080))

    def _publish_anchors_to_services(self) -> None:
        """Keep per-feature anchor dict refs aligned with orchestrator anchors."""
        anchors = self._anchors
        self.fishing._anchors = anchors
        self.auto_sell._anchors = anchors
        self.merchant._anchors = anchors
        self.snowman._anchors = anchors
        self.easter._anchors = anchors
        self.strange_controller._anchors = anchors
        self.biome_randomizer._anchors = anchors
        self.auto_rejoin._anchors = anchors
        self.auto_unequip._anchors = anchors
        self.auto_close_chat._anchors = anchors

    def _maybe_sync_anchor_screen_offset(self) -> None:
        """Map profile anchors to screen: scale to real client size, then ClientToScreen."""
        if not self._anchor_profile:
            return
        win = self._window_mgr.find_primary()
        if not win or not win.is_valid():
            return
        hwnd = win.hwnd
        cw, ch = RobloxWindow.get_client_size(hwnd)
        ox, oy = RobloxWindow.client_screen_origin(hwnd)
        key = (hwnd, ox, oy, cw, ch)
        if key == self._last_anchor_sync_key:
            return
        self._last_anchor_sync_key = key
        ref_w, ref_h = self._profile_reference_size
        mapped, sx, sy = _map_profile_anchors_to_screen(hwnd, self._anchor_profile, ref_w, ref_h)
        self._anchors = mapped
        self._alignment_info = {
            "client_size": [cw, ch],
            "reference_client": [ref_w, ref_h],
            "scale": [round(sx, 4), round(sy, 4)],
            "client_origin_screen": [ox, oy],
            "fishing_button_screen": self._anchors.get("fishing_button"),
            "fishing_cast_screen": self._anchors.get("fishing_cast_click"),
        }
        self._publish_anchors_to_services()

    def test_webhook(self) -> dict[str, Any]:
        """Send a test webhook with VaxiSols branding."""
        return self.webhooks.send_test(self._username)

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "last_error": self.last_error,
            "features": self.enabled_features,
            "plugin_status": self.plugin_status,
            "services": {
                "fishing": self.fishing.snapshot(),
                "auto_sell": self.auto_sell.snapshot(),
                "biome_aura": self.biome_aura.snapshot(),
                "merchant": self.merchant.snapshot(),
                "anti_afk": self.anti_afk.snapshot(),
                "snowman": self.snowman.snapshot(),
                "easter": self.easter.snapshot(),
                "strange_controller": self.strange_controller.snapshot(),
                "biome_randomizer": self.biome_randomizer.snapshot(),
                "auto_rejoin": self.auto_rejoin.snapshot(),
                "auto_unequip": self.auto_unequip.snapshot(),
                "auto_close_chat": self.auto_close_chat.snapshot(),
                "webhooks": self.webhooks.snapshot(),
            },
            "session": self.session.as_dict(),
            "cycle_count": self._cycle_count,
            "loop_count": self._casts_since_sell,
            "username": self._username,
            "alignment": dict(self._alignment_info) if self._alignment_info else None,
        }

    def build_session_report(self) -> dict[str, Any]:
        return self.snapshot()

    def _handle_event(self, event: dict[str, Any]) -> None:
        event["timestamp"] = int(time.time())
        self.session.push(event)
        self.webhooks.send_event(event, self._username)
        self.plugin_loader.run_hook("on_event", event)

    def _loop(self) -> None:
        """FishSol-style sequential main loop.

        Each iteration:
        1. Auto-crafter detection
        2. Focus window + Auto-sell cycle when thresholds met
        3. Fishing cast → bite → reel
        4. Timed inventory/pathing (SC, snowman, easter, BR) only during idle + grace window
        5. Failsafes + background timers (ClearUI, optional biome log reader, anti-AFK)
        """
        while not self._stop_event.is_set():
            try:
                if self._pause_event.is_set():
                    time.sleep(0.2)
                    continue

                now = time.time()
                elapsed = now - self._start_tick if self._start_tick else 0

                self._maybe_sync_anchor_screen_offset()

                # Keep Roblox focused for clicks (FishSol-style); throttled so UI stays usable.
                if (
                    (
                        self.enabled_features.get("fishing")
                        or self.enabled_features.get("auto_sell")
                        or self._is_pathing
                    )
                    and now - self._last_game_focus >= 2.0
                ):
                    self._last_game_focus = now
                    gw = self._window_mgr.find_primary()
                    if gw:
                        gw.bring_to_foreground()

                # Easter: mark pending/wait-before-pathing whenever interval hits, even mid-minigame.
                # Pathing executes later only inside ``_timed_inventory_safe``.
                if self.enabled_features.get("easter") and self.easter.should_run(elapsed):
                    if self.fishing._state == "reeling":
                        self.easter.pending = True
                    elif self._casts_since_sell >= self._sell_every_casts or self._restart_pathing:
                        self.easter.skip_fishing = True
                    else:
                        bobber_pos = self._anchors.get("fishing_bobber_detect")
                        if bobber_pos and self.fishing._screen.pixel_matches(
                            bobber_pos[0],
                            bobber_pos[1],
                            self.fishing.WHITE_PIXEL,
                            tolerance=10,
                        ):
                            self.easter.pending = True

                # ── 1. Auto-crafter detection ──
                if self.enabled_features.get("auto_crafter") and self._anchors:
                    for event in self.merchant.tick(True):
                        self._handle_event(event)

                # ── 3. Re-focus Roblox window periodically ──
                if now - self._last_refocus >= 8.0:
                    self._last_refocus = now
                    win = self._window_mgr.find_primary()
                    if win:
                        win.bring_to_foreground()

                # ── 4. Auto-sell cycle (when enough catches or restart triggered) ──
                # FishSol: loopCount only increments after a catch, NOT every tick
                if self._casts_since_sell >= self._sell_every_casts or self._restart_pathing:
                    self._restart_pathing = False

                    # Snowman delay (FishSol: if snowmanPathing, Sleep 2000)
                    if self.enabled_features.get("snowman"):
                        time.sleep(2.0)

                    if self._pathing_webhook:
                        self._handle_event({"type": "pathing_webhook", "message": "Starting Auto-Sell Pathing..."})

                    # Auto-unequip before pathing
                    for event in self.auto_unequip.run():
                        self._handle_event(event)

                    # Auto-close-chat before pathing
                    for event in self.auto_close_chat.run():
                        self._handle_event(event)

                    # Run the full sell cycle
                    self._is_pathing = True
                    for event in self.auto_sell.run_sell_cycle():
                        self._handle_event(event)
                    self._is_pathing = False
                    self._casts_since_sell = 0

                    # Easter skip-fishing: if easter was waiting for sell cycle
                    if self.easter.skip_fishing:
                        for event in self.easter.run():
                            self._handle_event(event)
                        self.easter.set_last_run(elapsed)
                        self.easter.skip_fishing = False
                        self._restart_pathing = True
                        continue

                # ── 4. Fishing cycle ──
                if self.enabled_features.get("fishing") and self._anchors:
                    for event in self.fishing.tick(now, True):
                        self._handle_event(event)
                        if event.get("type") == "fish_caught":
                            self._casts_since_sell += 1
                            self._cycle_count += 1

                    # Easter pending: run easter after fishing minigame finishes
                    if self.easter.pending:
                        for event in self.easter.run():
                            self._handle_event(event)
                        self.easter.set_last_run(elapsed)
                        self.easter.pending = False
                        self._restart_pathing = True
                        continue

                # ── Timed inventory / pathing features (FishSol timers) ──
                # Only when not fishing/minigame and startup grace elapsed — avoids SC/BR/etc.
                # blocking bites when strange_controller_time is 0.
                if self._timed_inventory_safe(now):
                    # Strange Controller (FishSol: SC Toggle)
                    if (
                        self.enabled_features.get("strange_controller")
                        and self.strange_controller.should_run(elapsed)
                    ):
                        for event in self.strange_controller.run():
                            self._handle_event(event)
                        self.strange_controller.set_last_run(elapsed)

                    # Snowman pathing (FishSol: Snowman Pathing Toggle)
                    if self.enabled_features.get("snowman") and self.snowman.should_run(elapsed):
                        if self._pathing_webhook:
                            self._handle_event(
                                {
                                    "type": "snowman_webhook",
                                    "message": "Starting snowman pathing...",
                                }
                            )
                        for event in self.snowman.run():
                            self._handle_event(event)
                        self.snowman.set_last_run(elapsed)
                        self._restart_pathing = True
                        continue

                    # Easter pathing: run heavy walk sequence only here (already pending/skip set above).
                    if (
                        self.enabled_features.get("easter")
                        and self.easter.should_run(elapsed)
                        and not self.easter.pending
                        and not self.easter.skip_fishing
                    ):
                        for event in self.easter.run():
                            self._handle_event(event)
                        self.easter.set_last_run(elapsed)
                        self._restart_pathing = True
                        continue

                    # Biome Randomizer (FishSol: BR Toggle)
                    if (
                        self.enabled_features.get("biome_randomizer")
                        and self.biome_randomizer.should_run(elapsed)
                    ):
                        for event in self.biome_randomizer.run():
                            self._handle_event(event)
                        self.biome_randomizer.set_last_run(elapsed)

                # ── 5. Failsafes ──
                # Auto-rejoin failsafe
                if self._global_failsafe_timer > 0:
                    failsafe_elapsed = now - self._global_failsafe_timer
                    if self.auto_rejoin.should_rejoin(failsafe_elapsed):
                        for event in self.auto_rejoin.run():
                            self._handle_event(event)
                        self._restart_pathing = True
                        self._global_failsafe_timer = 0

                # ── 6. Background timers ──
                # ClearUI timer (FishSol: SetTimer ClearUI, 15000)
                if self._anchors and now - self._last_clear_ui >= self._clear_ui_interval:
                    self._last_clear_ui = now
                    clear_ui = self._anchors.get("clear_ui_click")
                    if clear_ui:
                        self.fishing._input.click(clear_ui[0], clear_ui[1], jitter=False)

                # Biome / aura log + Bloxstrap RPC detection (toggle in Features)
                for event in self.biome_aura.tick(
                    self.enabled_features.get("biome_detector", True)
                ):
                    self._handle_event(event)

                # Anti-AFK
                for event in self.anti_afk.tick(now, self.enabled_features.get("anti_afk", True)):
                    self._handle_event(event)

                # Keep mouse near fishing bar area when not pathing
                if self._anchors and not self._is_pathing:
                    bar_sample = self._anchors.get("fishing_bar_color_sample")
                    if bar_sample and now - self._last_do_e >= 0.5:
                        self._last_do_e = now
                        self.fishing._input.move_to(
                            bar_sample[0] + 2, bar_sample[1] + 5, jitter=False
                        )

                # Small sleep to prevent CPU spinning (FishSol: Sleep 50 between checks)
                if self.fishing._state == "waiting_bite":
                    time.sleep(0.05)
                elif self.fishing._state == "idle":
                    time.sleep(0.1)

            except Exception as exc:
                self.last_error = str(exc)
                self.session.push({"type": "loop_error", "message": f"Loop error: {exc}", "timestamp": int(time.time())})
                time.sleep(0.5)

