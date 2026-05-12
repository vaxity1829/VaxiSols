from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CalibrationManager:
    def __init__(self, profiles_path: Path) -> None:
        self.profiles_path = profiles_path

    def load_profiles(self) -> dict[str, Any]:
        if not self.profiles_path.exists():
            return {"profiles": []}
        return json.loads(self.profiles_path.read_text(encoding="utf-8"))

    def save_anchor_point(
        self, profile_id: str, point_name: str, x: int, y: int
    ) -> dict[str, Any]:
        data = self.load_profiles()
        for profile in data.get("profiles", []):
            if profile.get("id") == profile_id:
                profile.setdefault("anchor_points", {})[point_name] = [x, y]
                break
        self.profiles_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data
