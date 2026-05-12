from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import request


MAX_DESC = 4096
MAX_TITLE = 256
EMBED_COLOR = 0xD32F2F

# Biome-specific embed colors
BIOME_COLORS = {
    "desert": 0xFFA500, "ocean": 0x0077BE, "forest": 0x228B22, "tundra": 0xB0E0E6,
    "volcano": 0xFB4F29, "cave": 0x696969, "jungle": 0x006400, "savanna": 0xBDB76B,
    "swamp": 0x4B5320, "mountain": 0x808080, "plains": 0x90EE90,
    "glitched": 0xFFFF00, "dreamspace": 0xFF00FF, "cyberspace": 0x00FFFF,
    "null": 0x808080, "corruption": 0x800080, "hell": 0xFF4500, "heaven": 0xFFE8A0,
    "windy": 0x9AE5FF, "rainy": 0x027CBD, "snowy": 0xDCEFF9, "sand storm": 0x8F7057,
    "starfall": 0x011AB7, "aurora": 0x0047AB, "singularity": 0xCF4023,
    "normal": 0xBFFF00, "eggland": 0xD4FC8D,
}

# Path to VaxiSols icon for webhook avatar
_ICON_PATH = Path(__file__).resolve().parent.parent / "VaxiSolsIcon.png"


@dataclass
class WebhookService:
    urls: list[str] = field(default_factory=list)
    private_server: str = ""
    sent_count: int = 0
    enabled: bool = True
    _avatar_set: bool = False

    def update_urls(self, urls: list[str]) -> None:
        self.urls = [url.strip() for url in urls if url.strip()]
        if self.urls and not self._avatar_set:
            self._set_avatar_on_webhooks()

    def _load_icon_base64(self) -> str | None:
        """Read the VaxiSols icon PNG and return as base64 data URI."""
        if not _ICON_PATH.exists():
            return None
        data = _ICON_PATH.read_bytes()
        return f"data:image/png;base64,{base64.b64encode(data).decode('ascii')}"

    def _set_avatar_on_webhooks(self) -> None:
        """PATCH each webhook to set its avatar to the VaxiSols icon."""
        avatar_data = self._load_icon_base64()
        if not avatar_data:
            return
        payload = json.dumps({"avatar": avatar_data}).encode("utf-8")
        for url in self.urls:
            # PATCH the webhook itself (same URL, PATCH method)
            req = request.Request(
                url=url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "VaxiSols/1.0"},
                method="PATCH",
            )
            try:
                with request.urlopen(req, timeout=5):
                    pass
            except Exception:
                pass
        self._avatar_set = True

    def _build_embed(self, event_type: str, message: str, username: str = "", event: dict[str, Any] | None = None) -> dict[str, Any]:
        title = f"VaxiSols | {event_type}"[:MAX_TITLE]
        color = EMBED_COLOR
        thumbnail = None
        
        # Build description with Discord timestamps
        desc = f"**Account:** `{username}`\n" if username else ""
        
        if event and event.get("event_type") == "merchant":
            # Merchant event (Jester/Mari)
            merchant_name = event.get("merchant_name", "Merchant")
            merchant_colors = {"Jester": 0xA352FF, "Mari": 0xFF82AB, "Rin": 0x5BC0DE, "Merchant": 0xFFD700}
            merchant_thumbnails = {
                "Jester": "https://raw.githubusercontent.com/cresqnt-sys/MultiScope/main/assets/jester_icon.png",
                "Mari": "https://raw.githubusercontent.com/cresqnt-sys/MultiScope/main/assets/mari_icon.png",
                "Rin": "https://raw.githubusercontent.com/cresqnt-sys/MultiScope/main/assets/rin_icon.png",
            }
            color = merchant_colors.get(merchant_name, 0x7289DA)
            thumbnail_url = merchant_thumbnails.get(merchant_name)
            if thumbnail_url:
                thumbnail = {"url": thumbnail_url}
            merchant_time = event.get("merchant_time", 0)
            if merchant_time:
                unix_ts = int(merchant_time)
                desc += f"**Detected At:** <t:{unix_ts}:F> (<t:{unix_ts}:R>)\n"
            if self.private_server:
                desc += f"**Private Server:** {self.private_server}\n"
        elif event and event.get("event_type") == "start":
            # Biome started
            biome_slug = (event.get("message", "") or "").replace("Biome Started: ", "").lower()
            color = BIOME_COLORS.get(biome_slug, EMBED_COLOR)
            start_time = event.get("biome_start_time", 0)
            if start_time:
                unix_ts = int(start_time)
                desc += f"**Started:** <t:{unix_ts}:F> (<t:{unix_ts}:R>)\n"
            desc += f"**Status:** Active\n"
            if self.private_server:
                desc += f"**Private Server:** {self.private_server}\n"
        elif event and event.get("event_type") == "end":
            # Biome ended
            biome_slug = (event.get("message", "") or "").replace("Biome Ended: ", "").lower()
            color = BIOME_COLORS.get(biome_slug, EMBED_COLOR)
            start_time = event.get("biome_start_time", 0)
            end_time = time.time()
            if start_time:
                unix_start = int(start_time)
                unix_end = int(end_time)
                duration_secs = int(end_time - start_time)
                mins = duration_secs // 60
                secs = duration_secs % 60
                desc += f"**Started:** <t:{unix_start}:F> (<t:{unix_start}:R>)\n"
                desc += f"**Ended:** <t:{unix_end}:F> (<t:{unix_end}:R>)\n"
                desc += f"**Duration:** {mins}m {secs}s\n"
            desc += f"**Status:** Ended\n"
        elif event and event.get("event_type") == "aura_equipped":
            aura_name = event.get("aura_name", "Unknown")
            color = 0x8E44AD
            aura_time = event.get("aura_time", 0)
            desc += f"**Aura:** `{aura_name}`\n"
            if aura_time:
                unix_ts = int(aura_time)
                desc += f"**Equipped At:** <t:{unix_ts}:F> (<t:{unix_ts}:R>)\n"
            if self.private_server:
                desc += f"**Private Server:** {self.private_server}\n"
        else:
            # Fallback for non-biome events
            desc += message[:MAX_DESC]
        
        desc = desc[:MAX_DESC]
        
        embed = {
            "title": title,
            "description": desc,
            "color": color,
            "footer": {"text": "VaxiSols"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if thumbnail:
            embed["thumbnail"] = thumbnail
        return embed

    def _post(self, payload_dict: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(payload_dict).encode("utf-8")
        results: list[dict[str, Any]] = []
        for url in self.urls:
            req = request.Request(
                url=url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "VaxiSols/1.0"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=5):
                    self.sent_count += 1
                    results.append({"url": url[:50] + "...", "ok": True})
            except Exception as exc:
                results.append({"url": url[:50] + "...", "ok": False, "error": str(exc)[:100]})
        all_ok = all(r["ok"] for r in results)
        return {"ok": all_ok, "results": results}

    def _post_to_private_server(self, payload_dict: dict[str, Any]) -> dict[str, Any]:
        """Send webhook payload to private server."""
        if not self.private_server:
            return {"ok": False, "error": "No private server configured"}
        
        payload = json.dumps(payload_dict).encode("utf-8")
        try:
            req = request.Request(
                url=self.private_server,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "VaxiSols/1.0"},
                method="POST",
            )
            with request.urlopen(req, timeout=5):
                self.sent_count += 1
                return {"ok": True, "url": self.private_server[:50] + "..."}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:100], "url": self.private_server[:50] + "..."}

    def send_event(self, event: dict[str, Any], username: str = "") -> None:
        if not self.enabled or (not self.urls and not self.private_server):
            return
        embed = self._build_embed(event.get("type", "event"), event.get("message", ""), username, event)
        
        # Send to public webhooks
        if self.urls:
            self._post({"username": "VaxiSols", "embeds": [embed]})
        
        # Send to private server
        if self.private_server:
            self._post_to_private_server({"username": "VaxiSols", "embeds": [embed]})

    def send_test(self, username: str = "") -> dict[str, Any]:
        if not self.urls:
            return {"ok": False, "error": "No webhook URLs configured"}
        # Ensure avatar is set before test
        if not self._avatar_set:
            self._set_avatar_on_webhooks()
        embed = self._build_embed("Test", "Webhook connected.", username, None)
        return self._post({"username": "VaxiSols", "embeds": [embed]})

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled, 
            "configured_urls": len(self.urls), 
            "private_server": bool(self.private_server),
            "sent_count": self.sent_count
        }
