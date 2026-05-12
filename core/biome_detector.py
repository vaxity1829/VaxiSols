from __future__ import annotations

import json
import os
import re
import sys
import ctypes
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.bloxstrap_rpc import aura_from_log_tail, aura_from_hover, biome_from_log_tail
from core.roblox_logs import list_biome_scan_log_paths, read_file_tail
from core.roblox_window import RobloxWindowManager
from integrations.webhooks import WebhookService


RARE_BIOMES = {"glitched", "dreamspace", "cyberspace", "null", "corruption", "hell", "heaven", "eggland"}

# Merchant names (display / webhook)
MERCHANT_NAMES = {"Jester", "Mari", "Rin", "Merchant"}

# Log-line patterns used by several Sol macro tools: named lines beat generic "merchant npc".
MERCHANT_LINE_NAMED_MS = re.compile(
    r"\[Merchant\]\s*:\s*(Jester|Mari|Rin)\s+has\s+arrived",
    re.IGNORECASE,
)
MERCHANT_LINE_NAMED_ALT = re.compile(
    r"\b(Jester|Mari|Rin)\b[^\n]{0,160}has\s+arrived\s+on\s+the\s+island",
    re.IGNORECASE,
)
MERCHANT_LINE_GENERIC_FLOG = re.compile(
    r"\[flog::output\][^\n]*merchant\s*npc",
    re.IGNORECASE,
)
AURA_EQUIP_PATTERNS = [
    re.compile(r"\bequipped\s+(?:an?\s+)?aura\b[:\s-]*(?P<aura>[A-Za-z0-9 _'\-]{2,64})", re.IGNORECASE),
    re.compile(r"\baura\s+equipped\b[:\s-]*(?P<aura>[A-Za-z0-9 _'\-]{2,64})", re.IGNORECASE),
    re.compile(r"\bequipped\b[:\s-]*(?P<aura>[A-Za-z0-9 _'\-]{2,64})\s+\baura\b", re.IGNORECASE),
]


def get_config_path() -> Path:
    """Get config path for portable mode (same directory as exe)."""
    # Try to get the directory where the executable is located
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        exe_dir = Path(sys.executable).parent
    else:
        # Running as script
        exe_dir = Path(__file__).parent.parent
    
    # Create config directory in exe location
    config_dir = exe_dir / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "default.json"


@dataclass
class AccountState:
    username: str
    window_hwnd: int = 0
    window_title: str = ""
    window_pid: int = 0
    last_biome: str = ""
    biome_history: list[str] = field(default_factory=list)
    biomes_detected: int = 0
    rare_biomes: int = 0
    last_tick: float = 0.0
    _last_biome_slug: str | None = None
    _last_webhook_biome: str | None = None
    _biome_start_time: float = 0.0
    _last_merchant_seen: dict[str, float] = field(default_factory=dict)  # merchant_name -> last_seen timestamp (cooldown)
    _merchant_baseline_done: bool = False
    _last_merchant_line_by_key: dict[str, str] = field(default_factory=dict)  # Jester|Mari|Rin|_generic -> full line
    _merchant_cooldown: float = 45.0  # seconds between re-notifying same merchant (safety net)
    _last_aura_seen: str = ""
    _last_aura_seen_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "window_hwnd": self.window_hwnd,
            "window_title": self.window_title,
            "window_pid": self.window_pid,
            "last_biome": self.last_biome,
            "biome_history": self.biome_history[-20:],
            "biomes_detected": self.biomes_detected,
            "rare_biomes": self.rare_biomes,
            "last_webhook_biome": self._last_webhook_biome,
            "biome_start_time": self._biome_start_time,
        }


@dataclass
class DetectorEvent:
    type: str
    message: str
    username: str
    biome: str = ""
    rare: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "message": self.message,
            "username": self.username,
            "biome": self.biome,
            "rare": self.rare,
            "timestamp": int(self.timestamp),
        }


class BiomeDetector:
    """Multi-account Sol's RNG detection engine. Tails Roblox logs per account for biome
    changes, merchant signals, and aura equips, with optional Discord webhooks."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.accounts: list[AccountState] = []
        self.webhooks = WebhookService()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.state: str = "stopped"
        self._tick_interval: float = 5.0
        self._events: list[DetectorEvent] = []
        self._max_events: int = 200
        self._start_time: float = 0.0
        self.feature_biome: bool = True
        self.feature_merchant: bool = True
        self.feature_aura: bool = True
        self.merchant_use_ocr: bool = False
        self.merchant_visual_fallback: bool = True
        self.load_config()

    def _push_event(self, ev: DetectorEvent) -> None:
        self._events.append(ev)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events // 2:]

    def load_config(self) -> None:
        """Load accounts and webhooks from config."""
        config_path = get_config_path()
        if not config_path.exists():
            return

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        # Load accounts
        self.accounts = [
            AccountState(
                username=acc.get("username", ""),
                window_hwnd=acc.get("window_hwnd", 0),
                window_title=acc.get("window_title", ""),
                window_pid=acc.get("window_pid", 0),
                last_biome=acc.get("last_biome", ""),
                biomes_detected=acc.get("biomes_detected", 0),
                rare_biomes=acc.get("rare_biomes", 0),
                biome_history=acc.get("biome_history", []),
                _last_webhook_biome=acc.get("last_webhook_biome", ""),
            )
            for acc in data.get("accounts", [])
        ]

        # Load webhooks
        self.webhooks.update_urls(data.get("webhooks", {}).get("urls", []))
        
        # Load private server
        private_server = data.get("private_server", "")
        self.webhooks.private_server = private_server.strip() if private_server.strip() else ""

        feat = data.get("detector_features") or {}
        self.feature_biome = bool(feat.get("biome", True))
        self.feature_merchant = bool(feat.get("merchant", True))
        self.feature_aura = bool(feat.get("aura", True))
        self.merchant_use_ocr = bool(feat.get("merchant_use_ocr", False))
        self.merchant_visual_fallback = bool(feat.get("merchant_visual_fallback", True))

    def start(self) -> None:
        if self.state == "running":
            return
        self._stop_event.clear()
        self.state = "running"
        self._start_time = time.time()
        self._events.clear()
        for acc in self.accounts:
            acc._last_biome_slug = None
            acc.last_tick = 0.0
            acc._merchant_baseline_done = False
            acc._last_merchant_line_by_key.clear()
        self._push_event(DetectorEvent(
            type="detector_start",
            message=f"Detection started ({len(self.accounts)} account(s))",
            username="",
            timestamp=time.time(),
        ))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.state = "stopped"
        self._push_event(DetectorEvent(
            type="detector_stop",
            message="Detection stopped",
            username="",
            timestamp=time.time(),
        ))

    def _scan_account(self, acc: AccountState) -> list[DetectorEvent]:
        events: list[DetectorEvent] = []
        paths = list_biome_scan_log_paths(username=acc.username, max_candidates=14)
        if not paths:
            return events

        mega = ""
        budget = 6 * 1024 * 1024
        for p in sorted(paths, key=lambda x: x.stat().st_mtime if x.exists() else 0):
            tail = read_file_tail(p, max_bytes=512 * 1024)
            if not tail:
                continue
            if len(mega) + len(tail) > budget:
                break
            mega += "\n" + tail

        slug, hover = biome_from_log_tail(mega)

        if self.feature_aura:
            aura_name = aura_from_log_tail(mega) or aura_from_hover(hover) or self._scan_aura_equipped_from_logs(mega)
            if aura_name:
                now = time.time()
                aura_key = aura_name.lower().strip()
                if aura_key != acc._last_aura_seen:
                    acc._last_aura_seen = aura_key
                    acc._last_aura_seen_at = now
                    events.append(
                        DetectorEvent(
                            type="aura_equipped",
                            message=f"{acc.username}: equipped aura {aura_name}",
                            username=acc.username,
                            biome=aura_name,
                            rare=False,
                            timestamp=now,
                        )
                    )
                    self.webhooks.send_event(
                        {
                            "type": "Aura Equipped",
                            "message": f"Aura Equipped: {aura_name}",
                            "event_type": "aura_equipped",
                            "aura_name": aura_name,
                            "aura_time": now,
                        },
                        username=acc.username,
                    )

        if self.feature_merchant:
            for ev in self._scan_merchants(acc, mega):
                events.append(ev)

        if self.feature_biome and slug and slug != acc._last_biome_slug:
            now = time.time()
            acc._last_biome_slug = slug
            acc.biomes_detected += 1
            acc.last_biome = slug
            acc.biome_history.append(slug)
            if len(acc.biome_history) > 100:
                acc.biome_history = acc.biome_history[-50:]
            rare = slug in RARE_BIOMES
            if rare:
                acc.rare_biomes += 1

            ev = DetectorEvent(
                type="biome_detected",
                message=f"{acc.username}: {slug}",
                username=acc.username,
                biome=slug,
                rare=rare,
                timestamp=now,
            )
            events.append(ev)

            # Send webhook if biome actually changed
            if slug != acc._last_webhook_biome:
                # Send "ended" webhook for previous biome
                if acc._last_webhook_biome and acc._biome_start_time > 0:
                    self.webhooks.send_event(
                        {
                            "type": f"{acc._last_webhook_biome} Ended",
                            "message": f"Biome Ended: {acc._last_webhook_biome}",
                            "biome_start_time": acc._biome_start_time,
                            "event_type": "end",
                        },
                        username=acc.username,
                    )

                # Send "started" webhook for new biome
                acc._last_webhook_biome = slug
                acc._biome_start_time = now
                self.webhooks.send_event(
                    {
                        "type": f"{slug} Started",
                        "message": f"Biome Started: {slug}",
                        "biome_start_time": now,
                        "event_type": "start",
                    },
                    username=acc.username,
                )

        return events

    @staticmethod
    def _collect_merchant_signals(mega: str) -> tuple[dict[str, str], str | None]:
        """Latest named merchant lines (MultiScope-style + alternates) and optional generic FLog merchant npc line."""
        lines = mega.split("\n")[-900:]
        named: dict[str, str] = {}
        generic: str | None = None

        for line in lines:
            s = line.strip()
            if not s:
                continue
            sl = s.lower()
            if "[flog::output]" not in sl and "[merchant]" not in sl:
                continue

            m = MERCHANT_LINE_NAMED_MS.search(s)
            if not m:
                m = MERCHANT_LINE_NAMED_ALT.search(s)
            if m:
                key = m.group(1).lower().capitalize()
                if key == "Jester" or key == "Mari" or key == "Rin":
                    named[key] = s
                continue

            if MERCHANT_LINE_GENERIC_FLOG.search(s):
                generic = s

        return named, generic

    def _scan_merchants(self, acc: AccountState, mega: str) -> list[DetectorEvent]:
        """Log-first merchant detection (matches patterns used by tools like MultiScope). Optional banner colors / OCR."""
        events: list[DetectorEvent] = []
        named, generic = self._collect_merchant_signals(mega)

        if not acc._merchant_baseline_done:
            acc._merchant_baseline_done = True
            for k, line in named.items():
                acc._last_merchant_line_by_key[k] = line
            if generic:
                acc._last_merchant_line_by_key["_generic"] = generic
            self._push_event(
                DetectorEvent(
                    type="info",
                    message=f"Merchant log baseline set for {acc.username}",
                    username=acc.username,
                    timestamp=time.time(),
                )
            )
            return events

        for name, line in named.items():
            if acc._last_merchant_line_by_key.get(name) != line:
                acc._last_merchant_line_by_key[name] = line
                self._fire_merchant_event(acc, name, events)

        if generic and acc._last_merchant_line_by_key.get("_generic") != generic:
            acc._last_merchant_line_by_key["_generic"] = generic
            if not named:
                resolved = self._resolve_merchant_optional_visual(acc)
                label = resolved if resolved else "Merchant"
                self._fire_merchant_event(acc, label, events)

        return events

    def _resolve_merchant_optional_visual(self, acc: AccountState) -> str | None:
        """When logs only say merchant npc: optional banner color scan, then OCR if enabled."""
        if not acc.window_hwnd or not ctypes.windll.user32.IsWindow(acc.window_hwnd):
            return None
        imgs = self._capture_merchant_regions(acc)
        if not imgs:
            return None
        chat_img, notif_img = imgs
        if self.merchant_visual_fallback:
            c = self._merchant_from_banner_colors(chat_img) or self._merchant_from_banner_colors(notif_img)
            if c:
                return c
        if self.merchant_use_ocr:
            o = self._merchant_from_ocr(chat_img) or self._merchant_from_ocr(notif_img)
            if o:
                return o
        return None

    def _capture_merchant_regions(self, acc: AccountState):
        try:
            from core.screen_reader import ScreenReader
            from core.roblox_window import RobloxWindow

            hwnd = acc.window_hwnd
            was_minimized = ctypes.windll.user32.IsIconic(hwnd)
            if was_minimized:
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                time.sleep(0.45)
            try:
                cw, ch = RobloxWindow.get_client_size(hwnd)
                reader = ScreenReader()
                chat_x = max(0, int(cw * 0.01))
                chat_y = max(0, int(ch * 0.40))
                chat_w = max(100, int(cw * 0.40))
                chat_h = max(50, int(ch * 0.55))
                notif_x = max(0, int(cw * 0.15))
                notif_y = max(0, int(ch * 0.02))
                notif_w = max(100, int(cw * 0.70))
                notif_h = max(50, int(ch * 0.25))
                chat_img = reader.capture_window_image(hwnd, chat_x, chat_y, chat_w, chat_h)
                notif_img = reader.capture_window_image(hwnd, notif_x, notif_y, notif_w, notif_h)
            finally:
                if was_minimized:
                    ctypes.windll.user32.ShowWindow(hwnd, 6)
            return (chat_img, notif_img)
        except Exception:
            return None

    @staticmethod
    def _merchant_from_banner_colors(img) -> str | None:
        if img is None:
            return None
        width, height = img.size
        purple_count = pink_count = cyan_count = 0
        sample_step = max(1, width // 50)
        for py in range(0, height, max(1, height // 15)):
            for px in range(0, width, sample_step):
                try:
                    r, g, b, *_ = img.getpixel((px, py))
                except Exception:
                    continue
                if r > 120 and g < 80 and b > 120:
                    purple_count += 1
                if r > 200 and g > 80 and g < 160 and b > 130:
                    pink_count += 1
                if r < 100 and g > 150 and b > 180:
                    cyan_count += 1
        threshold = max(3, (width * height) * 0.001)
        if purple_count > threshold and purple_count > pink_count and purple_count > cyan_count:
            return "Jester"
        if pink_count > threshold and pink_count > purple_count and pink_count > cyan_count:
            return "Mari"
        if cyan_count > threshold and cyan_count > purple_count and cyan_count > pink_count:
            return "Rin"
        return None

    @staticmethod
    def _merchant_from_ocr(img) -> str | None:
        if img is None:
            return None
        ocr_text = ""
        try:
            from rapidocr_onnxruntime import RapidOCR
            gray = img.convert("L")
            engine = RapidOCR()
            result, _ = engine(gray)
            if result:
                ocr_text = " ".join([item[1] for item in result if len(item) > 1]).strip().lower()
        except Exception:
            pass
        if not ocr_text.strip():
            try:
                import pytesseract
                from PIL import ImageEnhance, ImageFilter
                gray = img.convert("L")
                enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
                sharpened = enhanced.filter(ImageFilter.SHARPEN)
                ocr_text = pytesseract.image_to_string(sharpened).strip().lower()
            except Exception:
                pass
        for name in ("jester", "mari", "rin"):
            if name in ocr_text:
                return name.capitalize()
        if "merchant" in ocr_text:
            return "Merchant"
        return None

    def _fire_merchant_event(self, acc: AccountState, merchant_name: str, events: list[DetectorEvent]) -> None:
        """Fire a merchant detection event and webhook if not on cooldown."""
        now = time.time()
        last_seen = acc._last_merchant_seen.get(merchant_name, 0)
        if now - last_seen < acc._merchant_cooldown:
            return
        acc._last_merchant_seen[merchant_name] = now

        ev = DetectorEvent(
            type="merchant_detected",
            message=f"{acc.username}: {merchant_name} has arrived",
            username=acc.username,
            biome=merchant_name.lower(),
            rare=False,
            timestamp=now,
        )
        events.append(ev)
        self.webhooks.send_event(
            {
                "type": f"{merchant_name} Has Arrived",
                "message": f"Merchant Detected: {merchant_name}",
                "event_type": "merchant",
                "merchant_name": merchant_name,
                "merchant_time": now,
            },
            username=acc.username,
        )

    @staticmethod
    def _scan_aura_equipped_from_logs(mega: str) -> str | None:
        if not mega:
            return None
        lines = mega.split("\n")[-500:]
        for raw in reversed(lines):
            line = raw.strip()
            if not line:
                continue
            ll = line.lower()
            if "aura" not in ll and "equip" not in ll:
                continue
            for pat in AURA_EQUIP_PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                aura = " ".join((m.group("aura") or "").replace("`", "").split())
                aura = aura.strip(" .,:;!-[](){}")
                if len(aura) >= 2:
                    return aura
        return None

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                now = time.time()
                for acc in self.accounts:
                    if now - acc.last_tick < self._tick_interval:
                        continue
                    acc.last_tick = now
                    for ev in self._scan_account(acc):
                        self._push_event(ev)
                time.sleep(1.0)
            except Exception as exc:
                self._push_event(DetectorEvent(
                    type="error",
                    message=f"Scan error: {exc}",
                    username="",
                    timestamp=time.time(),
                ))
                time.sleep(1.0)

    def save_detector_features(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist biome / merchant / aura toggles and optional merchant OCR fallback flags."""
        if "biome" in payload:
            self.feature_biome = bool(payload["biome"])
        if "merchant" in payload:
            self.feature_merchant = bool(payload["merchant"])
        if "aura" in payload:
            self.feature_aura = bool(payload["aura"])
        if "merchant_use_ocr" in payload:
            self.merchant_use_ocr = bool(payload["merchant_use_ocr"])
        if "merchant_visual_fallback" in payload:
            self.merchant_visual_fallback = bool(payload["merchant_visual_fallback"])

        cfg = get_config_path()
        data: dict[str, Any] = {}
        if cfg.exists():
            try:
                raw = cfg.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
            except (json.JSONDecodeError, OSError):
                pass
        data["detector_features"] = {
            "biome": self.feature_biome,
            "merchant": self.feature_merchant,
            "aura": self.feature_aura,
            "merchant_use_ocr": self.merchant_use_ocr,
            "merchant_visual_fallback": self.merchant_visual_fallback,
        }
        tmp = cfg.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(cfg)
        return {"ok": True}

    def snapshot(self) -> dict[str, Any]:
        duration = time.time() - self._start_time if self._start_time else 0
        return {
            "state": self.state,
            "duration": round(duration, 1),
            "accounts": [a.to_dict() for a in self.accounts],
            "webhooks": self.webhooks.snapshot(),
            "webhook_urls": self.webhooks.urls,
            "private_server": self.webhooks.private_server,
            "recent_events": [e.to_dict() for e in self._events[-50:]],
            "detector_features": {
                "biome": self.feature_biome,
                "merchant": self.feature_merchant,
                "aura": self.feature_aura,
                "merchant_use_ocr": self.merchant_use_ocr,
                "merchant_visual_fallback": self.merchant_visual_fallback,
            },
        }

    def test_webhook(self) -> dict[str, Any]:
        return self.webhooks.send_test("VaxiSols")

    def add_account(self, username: str) -> dict[str, Any]:
        username = username.strip()
        if not username:
            return {"ok": False, "error": "Empty username"}
        if any(a.username == username for a in self.accounts):
            return {"ok": False, "error": "Account already exists"}
        self.accounts.append(AccountState(username=username))
        self._save_accounts()
        return {"ok": True}

    def remove_account(self, username: str) -> dict[str, Any]:
        self.accounts = [a for a in self.accounts if a.username != username]
        self._save_accounts()
        return {"ok": True}

    def _save_accounts(self) -> None:
        import json
        cfg = get_config_path()
        data: dict[str, Any] = {}
        if cfg.exists():
            try:
                raw = cfg.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
            except (json.JSONDecodeError, OSError):
                pass
        data["accounts"] = [
            {"username": a.username, "window_hwnd": a.window_hwnd, "window_title": a.window_title}
            for a in self.accounts
        ]
        tmp = cfg.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(cfg)

    def get_roblox_windows(self) -> list[dict[str, Any]]:
        """List all currently open Roblox windows for the window selector UI."""
        mgr = RobloxWindowManager()
        windows = mgr.find_all()
        return [
            {"hwnd": w.hwnd, "pid": w.pid, "title": w.title, "rect": [w.rect.left, w.rect.top, w.rect.right, w.rect.bottom]}
            for w in windows
        ]

    def set_account_window(self, username: str, hwnd: int, pid: int = 0) -> dict[str, Any]:
        """Assign a Roblox window (by hwnd) to an account."""
        import ctypes
        user32 = ctypes.windll.user32
        
        for acc in self.accounts:
            if acc.username == username:
                acc.window_hwnd = hwnd
                if pid:
                    acc.window_pid = pid
                else:
                    process_id = ctypes.wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
                    acc.window_pid = process_id.value
                
                # Look up window title
                mgr = RobloxWindowManager()
                for w in mgr.find_all():
                    if w.hwnd == hwnd:
                        acc.window_title = w.title
                        break
                else:
                    # Get window title directly
                    title_buf = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd, title_buf, 256)
                    acc.window_title = title_buf.value
                
                self._save_accounts()
                return {"ok": True}
        return {"ok": False, "error": "Account not found"}

    def pick_window(self) -> dict[str, Any]:
        """Open a window picker to select a Roblox window by focusing."""
        import ctypes
        import ctypes.wintypes as wt
        import time

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Create a simple message box to instruct user
        MB_OK = 0x00000000
        MB_ICONINFORMATION = 0x00000040
        result = user32.MessageBoxW(
            0,
            "Click OK, then focus on the Roblox window you want to select.\n\nThe window will be selected after 3 seconds.",
            "Window Picker",
            MB_OK | MB_ICONINFORMATION
        )
        
        # If user cancels, return early
        if result != 1:
            return {"ok": False, "error": "User cancelled window selection"}

        # Wait 3 seconds for user to focus window
        time.sleep(3)

        # Get the currently focused window
        hwnd = user32.GetForegroundWindow()

        # Check if it's a Roblox window
        if hwnd:
            # Get window title first
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buf, 256)
            window_title = title_buf.value
            
            # Get process ID for duplicate checking
            process_id = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            process_id = process_id.value
            
            # Check if this window is already assigned to another account
            for acc in self.accounts:
                if acc.window_hwnd == hwnd:
                    return {"ok": False, "error": f"This window is already assigned to account: {acc.username}"}
                if hasattr(acc, 'window_pid') and acc.window_pid == process_id:
                    return {"ok": False, "error": f"This process is already assigned to account: {acc.username}"}
            
            # Check window title for "Roblox" (case insensitive)
            if window_title and "roblox" in window_title.lower():
                return {"ok": True, "hwnd": hwnd, "title": window_title, "pid": process_id}
            
            # Fallback: check process name for RobloxPlayerBeta.exe
            try:
                import psutil
                if process_id:
                    process = psutil.Process(process_id)
                    process_name = process.name().lower()
                    if "robloxplayerbeta.exe" in process_name.lower():
                        title = window_title if window_title else "RobloxPlayerBeta"
                        return {"ok": True, "hwnd": hwnd, "title": title, "pid": process_id}
            except Exception:
                pass
            
            return {"ok": False, "error": f"Selected window is not a Roblox window (title: '{window_title}')"}
        else:
            return {"ok": False, "error": "No focused window found"}
