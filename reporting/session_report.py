from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionReport:
    started_at: datetime | None = None
    ended_at: datetime | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def begin(self) -> None:
        if self.started_at is None:
            self.started_at = datetime.now()
        self.ended_at = None

    def end(self) -> None:
        self.ended_at = datetime.now()

    def push(self, event: dict[str, Any]) -> None:
        if len(self.events) > 500:
            self.events.pop(0)
        self.events.append(event)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self._duration_seconds(),
            "event_count": len(self.events),
            "recent_events": self.events[-25:],
        }

    def _duration_seconds(self) -> int:
        if not self.started_at:
            return 0
        end = self.ended_at or datetime.now()
        return int((end - self.started_at).total_seconds())
