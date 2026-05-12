from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from core.bloxstrap_rpc import biome_from_log_tail
from core.roblox_logs import list_biome_scan_log_paths, read_file_tail


RARE_BIOMES = {"glitched", "dreamspace", "cyberspace", "null", "corruption", "hell", "heaven"}


@dataclass
class BiomeAuraStats:
    biomes_detected: int = 0
    auras_detected: int = 0
    rare_biomes: int = 0
    rare_auras: int = 0
    last_biome: str = ""
    last_aura: str = ""
    biome_history: list[str] = field(default_factory=list)
    aura_history: list[str] = field(default_factory=list)
    merchants_from_log: int = 0


class BiomeAuraService:
    name = "biome_aura"

    def __init__(self) -> None:
        self.stats = BiomeAuraStats()
        self._last_tick = 0.0
        self._tick_interval = 0.5
        self._username_hint: str | None = None
        self._last_biome_slug: str | None = None
        self._last_scanned_paths: list[Path] = []

    def configure(self, username: str | None) -> None:
        self._username_hint = (username or "").strip() or None

    def reset_session(self) -> None:
        self._last_biome_slug = None

    def tick(self, active: bool) -> list[dict[str, str]]:
        if not active:
            return []
        now = time.time()
        if now - self._last_tick < self._tick_interval:
            return []
        self._last_tick = now

        events: list[dict[str, str]] = []
        paths = list_biome_scan_log_paths(username=self._username_hint, max_candidates=14)
        self._last_scanned_paths = paths
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

        slug, _hover = biome_from_log_tail(mega)
        if slug and slug != self._last_biome_slug:
            self._last_biome_slug = slug
            self.stats.biomes_detected += 1
            self.stats.last_biome = slug
            self.stats.biome_history.append(slug)
            if len(self.stats.biome_history) > 100:
                self.stats.biome_history = self.stats.biome_history[-50:]
            rare = slug in RARE_BIOMES
            if rare:
                self.stats.rare_biomes += 1
            events.append(
                {
                    "type": "biome_detected",
                    "message": f"Biome (bloxstrap_rpc): {slug}",
                    "biome": slug,
                    "source": "bloxstrap_rpc",
                    "rare": str(rare).lower(),
                }
            )

        return events

    def snapshot(self) -> dict:
        return {
            "biomes_detected": self.stats.biomes_detected,
            "auras_detected": self.stats.auras_detected,
            "rare_biomes": self.stats.rare_biomes,
            "rare_auras": self.stats.rare_auras,
            "last_biome": self.stats.last_biome,
            "last_aura": self.stats.last_aura,
            "biome_history": self.stats.biome_history[-10:],
            "aura_history": self.stats.aura_history[-10:],
            "merchants_from_log": self.stats.merchants_from_log,
            "scanned_logs": [str(p) for p in self._last_scanned_paths[:5]],
        }
